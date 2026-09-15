"""Check one agent turn against the chain, right after the turn.

The agent's reply is text. The chain is the record. This compares the two the same way the
evaluation does, so every turn carries its own verdict: a scan turn is judged by value (the
dollar total the agent reported against what the verified tools compute), and a claim turn is
judged by its receipts (what the agent said happened against what the transactions did).

The verdict goes to PRISM with the trace, as metadata and as a span, so the traces that need
attention can be found by filtering instead of by reading every reply.
"""

from __future__ import annotations

from ..chain import Chain
from .runner import FAILURE_WORDS, SUCCESS_WORDS, reported_usd, tx_outcomes

CLAIM_TOOLS = ("collect_fees", "claim_airdrop")


def check_turn(turn: dict, wallet: str | None, chain: Chain) -> dict | None:
    """Return {kind, ok, text, ...} for a scan or claim turn, None when the turn made no checkable claim."""
    names = [c["name"] for c in turn["tool_calls"]]
    reply = turn["reply"]

    if any(n in CLAIM_TOOLS for n in names):
        outcomes = tx_outcomes(turn, chain)
        any_success = any(o["status"] == "success" for o in outcomes)
        positive, negative = bool(SUCCESS_WORDS.search(reply)), bool(FAILURE_WORDS.search(reply))
        received = round(sum((o.get("usd_received") or 0.0) for o in outcomes), 2)
        summary = ", ".join(f"{o['tool']} {o['status']}" for o in outcomes)
        base = {"kind": "receipts", "outcomes": outcomes, "usd_received": received}
        if positive and not negative and not any_success:
            return {**base, "ok": False, "text": f"Does not match the receipts. The agent said it claimed, but every transaction failed: {summary}."}
        if not positive and any_success:
            return {**base, "ok": False, "text": f"Does not match the receipts. A transaction succeeded ({summary}) but the agent did not report it."}
        return {**base, "ok": True, "text": f"Matches the receipts: {summary}" + (f", ${received:,.2f} received." if received else ".")}

    if "scan_wallet" not in names or not wallet:
        return None
    from ..tools import airdrops, uniswap

    fees = uniswap.scan_fees(wallet)
    drops = airdrops.scan_airdrops(wallet)
    truth = round(fees["usd_total"] + drops["usd_total"], 2)
    reported = reported_usd(reply)
    ok = (reported is None or reported < 1.0) if truth == 0 else (reported is not None and abs(reported - truth) / truth <= 0.05)
    said = "no dollar figure" if reported is None else f"${reported:,.2f}"
    text = ("Matches the chain. " if ok else "Does not match the chain. ") + f"Chain says ${truth:,.2f} claimable, the agent said {said}."
    return {"kind": "value", "ok": ok, "text": text, "wallet": wallet, "truth_usd": truth, "reported_usd": reported}
