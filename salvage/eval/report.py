"""Before and after: compare the latest v1 run with the latest v2 run."""

from __future__ import annotations

import json
from pathlib import Path

from .runner import latest_run


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def compare(v1_path: Path | None = None, v2_path: Path | None = None) -> str:
    v1_path = v1_path or latest_run("v1")
    v2_path = v2_path or latest_run("v2")
    if not v1_path or not v2_path:
        return "need one v1 run and one v2 run first (salvage eval v1, salvage eval v2)"
    a, b = load(v1_path)["summary"], load(v2_path)["summary"]
    rows = [
        ("Wallets scored", a["wallets"], b["wallets"]),
        ("Reported value within 5% of the chain", f"{a['value_accuracy_pct']}%", f"{b['value_accuracy_pct']}%"),
        ("Mean absolute error (USD)", f"${a['mean_abs_error_usd']:,.2f}", f"${b['mean_abs_error_usd']:,.2f}"),
        ("Largest error (USD)", f"${a['max_abs_error_usd']:,.2f}", f"${b['max_abs_error_usd']:,.2f}"),
        ("Phantom successes (said claimed, nothing succeeded)", a["phantom_success_count"], b["phantom_success_count"]),
        ("Claim reports matching receipts", f"{a['claim_report_accuracy_pct']}%", f"{b['claim_report_accuracy_pct']}%"),
    ]
    lines = ["| Metric | v1 (naive) | v2 (verified) |", "|---|---|---|"]
    lines += [f"| {m} | {x} | {y} |" for m, x, y in rows]
    lines.append("")
    lines.append("| Cohort | v1 value ok | v2 value ok | v1 phantom | v2 phantom |")
    lines.append("|---|---|---|---|---|")
    for cohort in sorted(set(a["by_cohort"]) | set(b["by_cohort"])):
        ca, cb = a["by_cohort"].get(cohort, {"n": 0, "value_ok": 0, "phantom": 0}), b["by_cohort"].get(cohort, {"n": 0, "value_ok": 0, "phantom": 0})
        lines.append(f"| {cohort} | {ca['value_ok']}/{ca['n']} | {cb['value_ok']}/{cb['n']} | {ca['phantom']} | {cb['phantom']} |")
    lines.append("")
    lines.append(f"v1 run: {v1_path.name}   v2 run: {v2_path.name}")
    return "\n".join(lines)


def evidence_bundle(out_path: Path) -> Path:
    """Write a judge friendly summary: the before and after table, the sessions to open in PRISM,
    the worst replies, and every phantom success with its transaction status."""
    from ..config import settings

    v1_path, v2_path = latest_run("v1"), latest_run("v2")
    lines = ["# Salvage evidence", ""]
    lines.append(f"PRISM project `{settings.prism_project_id}`, agents `salvage_v1` and `salvage_v2`, one session per wallet.")
    lines.append("Runs: " + ", ".join(p.name for p in (v1_path, v2_path) if p) + ".")
    lines += ["", "## Before and after", "", compare(v1_path, v2_path), ""]
    for version, path in (("v1", v1_path), ("v2", v2_path)):
        if not path:
            continue
        results = load(path)["results"]
        lines += [f"## {version}: sessions worth opening in PRISM", ""]
        lines.append("| wallet | cohort | chain says | agent said | claim outcomes | PRISM session |")
        lines.append("|---|---|---|---|---|---|")
        for r in sorted(results, key=lambda r: -r["score"]["abs_error_usd"]):
            s = r["score"]
            flag = " (phantom success)" if s["phantom_success"] else ""
            reported = "none" if s["reported_usd"] is None else f"${s['reported_usd']:,.2f}"
            outcomes = ", ".join(o["status"] for o in r["outcomes"]) or "no claim attempted"
            lines.append(f"| {r['label']} | {r['cohort']} | ${s['truth_usd']:,.2f} | {reported}{flag} | {outcomes} | `{r['session_id']}` |")
        lines.append("")
        bad = [r for r in results if not r["score"]["value_ok"] or r["score"]["phantom_success"]]
        if bad:
            lines += [f"### {version}: what it actually said", ""]
            for r in sorted(bad, key=lambda r: -r["score"]["abs_error_usd"])[:4]:
                lines.append(f"**{r['label']}** (chain says ${r['score']['truth_usd']:,.2f}), first reply:")
                lines.append("")
                lines.append("> " + r["turn1"]["reply"].strip().replace("\n", "\n> "))
                lines.append("")
                if r["score"]["phantom_success"]:
                    lines.append("Second reply, after the claim transaction reverted:")
                    lines.append("")
                    lines.append("> " + r["turn2"]["reply"].strip().replace("\n", "\n> "))
                    lines.append("")
    out_path.write_text("\n".join(lines))
    return out_path


def worst_examples(version: str, k: int = 3) -> list[dict]:
    path = latest_run(version)
    if not path:
        return []
    results = load(path)["results"]
    bad = [r for r in results if not r["score"]["value_ok"] or r["score"]["phantom_success"]]
    bad.sort(key=lambda r: -r["score"]["abs_error_usd"])
    return [{"label": r["label"], "truth": r["score"]["truth_usd"], "reported": r["score"]["reported_usd"],
             "phantom": r["score"]["phantom_success"], "reply1": r["turn1"]["reply"][:400], "reply2": r["turn2"]["reply"][:300]} for r in bad[:k]]
