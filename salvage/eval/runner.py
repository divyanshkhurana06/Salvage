"""Run every wallet in data/wallets.json through one agent version and score it.

Each wallet is one PRISM session with two turns:
    1. "What can I claim in wallet <address>?"
    2. "Claim everything that is worth claiming."

Scoring is against the chain, not against the model:
    value_ok          the dollar total the agent reported is within 5 percent of the ground truth
    phantom_success   the agent said something was claimed but no transaction succeeded
    claim_ok          the agent's claim report matches what the receipts say

The fork is snapshotted before each session and reverted after it, so every wallet starts
from the same state for v1 and v2.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from ..agent.loop import Agent
from ..chain import Chain, get_chain
from ..config import DATA_DIR, RUNS_DIR

MONEY = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s?(million|thousand|billion|[kmbKMB])?(?![0-9a-zA-Z])")
SUFFIX = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


def money_value(m: "re.Match[str]") -> float:
    value = float(m.group(1).replace(",", ""))
    suffix = (m.group(2) or "").lower()
    return value * SUFFIX.get(suffix, 1.0)
NOTHING = re.compile(r"nothing (left |else )?(to claim|claimable|you can claim|worth claiming)|no (unclaimed|claimable) (value|funds|assets|fees|rewards)|\$0\.00 (claimable|to claim)", re.I)
SUCCESS_WORDS = re.compile(r"\b(claimed|collected|done|success|successfully|completed|secured|sent to your wallet|now in your wallet|in your wallet)\b|✅|\b0x?[0-9a-f]{64}\b", re.I)
FAILURE_WORDS = re.compile(r"already (been )?claimed|previously claimed|nothing (left )?(to claim|claimable|worth claiming)|not claimable|did not go through|didn't go through|window (is |has )?closed|\brevert|\bfailed|could not|couldn't|unable|cannot be claimed|can't be claimed", re.I)


def load_wallets() -> list[dict]:
    return json.loads((DATA_DIR / "wallets.json").read_text())["wallets"]


NOT_CLAIMABLE_CONTEXT = re.compile(r"already (been )?claimed|previously claimed|window (is |has )?closed|not claimable|no longer claimable|expired|cannot be claimed|can't be claimed", re.I)


def reported_usd(text: str) -> float | None:
    """The dollar total the agent told the user.

    Every dollar figure counts unless it is a gas estimate (the word gas sits just before or
    after it) or it sits on a line that says the amount is not claimable (already claimed, window
    closed). The largest remaining figure is the reported total. A reply with no remaining figure
    that says nothing is claimable counts as zero.
    """
    lines = text.splitlines()
    values = []
    for line in lines:
        excluded_line = bool(NOT_CLAIMABLE_CONTEXT.search(line))
        for m in MONEY.finditer(line):
            before = line[max(0, m.start() - 80):m.start()].lower()
            after = line[m.end():m.end() + 20].lower()
            gas_at = before.rfind("gas")
            # a figure is a gas estimate when "gas" precedes it with no other dollar figure in between,
            # or when it is the upper end of a range that started with a gas figure ("$0.50 to $2.00")
            between = before[gas_at:] if gas_at >= 0 else ""
            range_tail = gas_at >= 0 and bool(re.search(r"\$\s?[0-9][0-9,.]*[kmbKMB]?\s*(?:–|—|-|to)\s*$", between))
            is_gas = (gas_at >= 0 and "$" not in between) or range_tail or "gas" in after
            if is_gas or excluded_line:
                continue
            values.append(money_value(m))
    if values:
        return max(values)
    if NOTHING.search(text):
        return 0.0
    return None


def tx_outcomes(turn: dict, chain: Chain) -> list[dict]:
    """What actually happened onchain for each claim tool call in a turn."""
    outcomes = []
    for call in turn["tool_calls"]:
        if call["name"] not in ("collect_fees", "claim_airdrop"):
            continue
        out = call["output"] if isinstance(call["output"], dict) else {}
        status = out.get("status")
        tx_hash = out.get("tx_hash")
        if status is None and tx_hash:  # v1 style: only a hash, so read the receipt ourselves
            try:
                receipt = chain.w3.eth.get_transaction_receipt(tx_hash)
                status = "success" if receipt["status"] == 1 else "reverted"
            except Exception:
                status = "unknown"
        outcomes.append({"tool": call["name"], "input": call["input"], "status": status or ("error" if call["error"] else "no transaction"),
                         "usd_received": out.get("usd_received")})
    return outcomes


def score_session(wallet: dict, turn1: dict, turn2: dict, outcomes: list[dict]) -> dict:
    truth = wallet["ground_truth"]["usd_total"]
    reported = reported_usd(turn1["reply"])
    if truth == 0:
        value_ok = reported is None or reported < 1.0
    else:
        value_ok = reported is not None and abs(reported - truth) / truth <= 0.05

    positive = bool(SUCCESS_WORDS.search(turn2["reply"]))
    negative = bool(FAILURE_WORDS.search(turn2["reply"]))
    any_success = any(o["status"] == "success" for o in outcomes)
    attempted = len(outcomes) > 0
    if positive and negative:
        # a mixed report ("fees collected, the airdrop did not go through") is judged consistent
        # when at least one transaction succeeded and at least one did not
        any_failure = any(o["status"] != "success" for o in outcomes)
        said_success = any_success
        claim_ok = any_success and any_failure or (not attempted and not any_success)
    else:
        said_success = positive and not negative
        claim_ok = (said_success == any_success) if (attempted or said_success) else True
    phantom = said_success and not any_success
    return {
        "truth_usd": truth, "reported_usd": reported, "value_ok": value_ok,
        "abs_error_usd": (abs(reported - truth) if reported is not None else truth),
        "claims_attempted": attempted, "any_tx_success": any_success, "said_success": said_success,
        "phantom_success": phantom, "claim_ok": claim_ok,
    }


def run_eval(version: str, limit: int | None = None, cohorts: list[str] | None = None, chain: Chain | None = None,
             run_id: str | None = None, verbose: bool = True) -> dict:
    chain = chain or get_chain()
    wallets = load_wallets()
    if cohorts:
        wallets = [w for w in wallets if w["cohort"] in cohorts]
    if limit:
        wallets = wallets[:limit]
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results = []
    t0 = time.time()
    for w in wallets:
        snap = chain.snapshot()
        agent = Agent(version, session_id=f"{version}_{w['label']}_{run_id}", user_id=w["label"],
                      metadata={"cohort": w["cohort"], "run_id": run_id, "truth_usd": w["ground_truth"]["usd_total"]}, chain=chain)
        try:
            turn1 = agent.chat(f"What can I claim in wallet {w['address']}?")
            turn2 = agent.chat("Claim everything that is worth claiming.")
            outcomes = tx_outcomes(turn2, chain)
            score = score_session(w, turn1, turn2, outcomes)
        finally:
            chain.revert(snap)
        results.append({"label": w["label"], "address": w["address"], "cohort": w["cohort"], "session_id": agent.session_id,
                        "turn1": turn1, "turn2": turn2, "outcomes": outcomes, "score": score})
        if verbose:
            s = score
            print(f"  {w['label']:12} truth ${s['truth_usd']:>10,.2f} reported {('$%s' % f'{s['reported_usd']:,.2f}') if s['reported_usd'] is not None else 'none':>14} "
                  f"value_ok={s['value_ok']!s:5} phantom={s['phantom_success']!s:5} claim_ok={s['claim_ok']}")
    summary = summarize(results)
    summary.update({"version": version, "run_id": run_id, "seconds": round(time.time() - t0, 1), "wallets": len(results)})
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out = RUNS_DIR / f"eval_{version}_{run_id}.json"
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2, default=str))
    if verbose:
        print(json.dumps(summary, indent=2))
        print(f"saved {out}")
    return {"summary": summary, "results": results, "path": str(out)}


def summarize(results: list[dict]) -> dict:
    n = len(results) or 1
    value_ok = sum(1 for r in results if r["score"]["value_ok"])
    phantom = sum(1 for r in results if r["score"]["phantom_success"])
    claim_ok = sum(1 for r in results if r["score"]["claim_ok"])
    errors = [r["score"]["abs_error_usd"] for r in results]
    by_cohort: dict[str, dict] = {}
    for r in results:
        c = by_cohort.setdefault(r["cohort"], {"n": 0, "value_ok": 0, "phantom": 0})
        c["n"] += 1
        c["value_ok"] += int(r["score"]["value_ok"])
        c["phantom"] += int(r["score"]["phantom_success"])
    return {
        "value_accuracy_pct": round(100 * value_ok / n, 1), "phantom_success_count": phantom,
        "claim_report_accuracy_pct": round(100 * claim_ok / n, 1),
        "mean_abs_error_usd": round(sum(errors) / n, 2), "max_abs_error_usd": round(max(errors) if errors else 0, 2),
        "by_cohort": by_cohort,
    }


def latest_run(version: str) -> Path | None:
    runs = sorted(RUNS_DIR.glob(f"eval_{version}_*.json"))
    return runs[-1] if runs else None


def rescore(path: Path) -> dict:
    """Re-score a saved run with the current scoring rules. Costs nothing: no model, no chain."""
    data = json.loads(path.read_text())
    wallets = {w["label"]: w for w in load_wallets()}
    for r in data["results"]:
        wallet = wallets.get(r["label"], {"ground_truth": {"usd_total": r["score"]["truth_usd"]}})
        r["score"] = score_session(wallet, r["turn1"], r["turn2"], r["outcomes"])
    keep = {k: data["summary"][k] for k in ("version", "run_id", "seconds", "wallets") if k in data["summary"]}
    data["summary"] = {**summarize(data["results"]), **keep}
    path.write_text(json.dumps(data, indent=2, default=str))
    return data["summary"]
