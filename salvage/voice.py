"""Voice: the ElevenLabs agent talks to a user, and calls these endpoints as its tools.

The conversation itself runs on ElevenLabs. What runs here is the same verified v2 tool
layer the text agent uses, keyed by the ElevenLabs conversation id so a call is one session.
Every tool call is also sent to PRISM as a trace with a tool span, under agent id
salvage_voice, so the call shows up in PRISM even before the post call webhook arrives.

Wallets are referred to by short names in speech ("fees eight", "both one") because nobody
can say a 40 character address. resolve_wallet maps those names to the wallet set.
"""

from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter
from pydantic import BaseModel

from .agent.tools_schema import Executors
from .chain import get_chain
from .config import DATA_DIR
from .prism.tracer import Span, SpanClock, get_tracer

router = APIRouter(prefix="/api/voice", tags=["voice"])
STATE: dict[str, dict] = {}  # conversation_id -> {"active_wallet": ...}

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16}
COHORT_WORDS = {"both": "both", "fees": "fees", "fee": "fees", "airdrop": "airdrop", "claimed": "claimed", "expired": "expired", "empty": "empty"}


def _wallets() -> list[dict]:
    path = DATA_DIR / "wallets.json"
    return json.loads(path.read_text())["wallets"] if path.exists() else []


def resolve_wallet(text: str | None, conversation_id: str) -> str | None:
    """An address, a label like fees_08, or spoken words like 'fees eight'. Falls back to the active wallet."""
    text = (text or "").strip()
    m = re.search(r"0x[a-fA-F0-9]{40}", text)
    if m:
        return m.group(0)
    lowered = text.lower().replace("_", " ").replace("-", " ")
    number = None
    for tok in lowered.split():
        if tok.isdigit():
            number = int(tok)
        elif tok in WORDS:
            number = WORDS[tok]
    cohort = next((v for k, v in COHORT_WORDS.items() if k in lowered), None)
    if cohort and number is not None:
        label = f"{cohort}_{number:02d}"
        for w in _wallets():
            if w["label"] == label:
                return w["address"]
    if number is not None and not cohort:  # "wallet eight" means the eighth in the list
        ws = _wallets()
        if 1 <= number <= len(ws):
            return ws[number - 1]["address"]
    return STATE.get(conversation_id, {}).get("active_wallet")


def _executors(conversation_id: str) -> dict:
    state = STATE.setdefault(conversation_id, {"active_wallet": None})
    return Executors("v2", get_chain(), state).mapping()


def _trace(conversation_id: str, tool: str, args: dict, result: dict, spoken: str, clock: SpanClock) -> None:
    end, dur = clock.finish()
    span = Span(name=f"tool:{tool}", span_type="tool", input_text=json.dumps(args), output_text=json.dumps(result, default=str)[:6000],
                start_time=clock.start_iso, end_time=end, duration_ms=dur)
    try:
        get_tracer().record_turn(
            session_id=conversation_id or f"voice_{int(time.time())}", agent_id="salvage_voice", agent_name="Salvage voice",
            model="elevenlabs-agent", input_messages=[{"role": "user", "content": f"[voice tool request {tool}] {json.dumps(args)}"}],
            output_text=spoken, latency_ms=int(dur), spans=[span],
            metadata={"agent_version": "voice", "source": "elevenlabs", "wallet": STATE.get(conversation_id, {}).get("active_wallet") or ""},
        )
    except Exception as exc:  # tracing must never break a live call
        print(f"[voice] prism trace failed: {exc}")


def _dollars(x: float | None) -> str:
    return "an unknown dollar value" if x is None else f"{x:,.2f} dollars"


class ScanIn(BaseModel):
    conversation_id: str = ""
    wallet: str = ""


class ClaimIn(BaseModel):
    conversation_id: str = ""
    what: str = "everything"


@router.post("/scan")
def scan(body: ScanIn) -> dict:
    clock = SpanClock()
    address = resolve_wallet(body.wallet, body.conversation_id)
    if not address:
        spoken = "I did not catch which wallet. Say a wallet name like fees eight or both one, or paste an address in the app."
        return {"ok": False, "say": spoken}
    ex = _executors(body.conversation_id)
    result = ex["scan_wallet"](address)
    label = next((w["label"].replace("_", " ") for w in _wallets() if w["address"].lower() == address.lower()), address[:8])
    fees = result["uniswap"]
    drops = result["airdrops"]
    parts = []
    for p in fees["positions"]:
        if p["usd_total"] > 0:
            parts.append(f"Uniswap fees on position {p['token_id']} worth {_dollars(p['usd_total'])}")
    for d in drops["airdrops"]:
        parts.append(f"airdrop {d['name']} of {d['amount_units']:.2f} {d['symbol']}, {_dollars(d['usd'])}, status {d['status']}")
    total = result["usd_total"]
    if total <= 0:
        spoken = f"Wallet {label} has nothing claimable right now." + (" " + "; ".join(parts) + "." if parts else "")
    else:
        spoken = f"Wallet {label} can claim {_dollars(total)} in total: " + "; ".join(parts) + "."
    out = {"ok": True, "wallet": address, "label": label, "usd_total": total, "say": spoken, "details": result["summary"]}
    _trace(body.conversation_id, "scan_wallet", {"wallet": body.wallet, "resolved": address}, out, spoken, clock)
    return out


@router.post("/gas")
def gas(body: ClaimIn) -> dict:
    clock = SpanClock()
    ex = _executors(body.conversation_id)
    g = ex["estimate_gas_cost"]()
    if g.get("actions"):
        spoken = "; ".join(f"{a['action']} is worth {_dollars(a['value_usd'])} and costs {_dollars(a['gas_usd'])} in gas, net {_dollars(a['net_usd'])}" for a in g["actions"])
        spoken += f". In total {_dollars(g['total_value_usd'])} of value for {_dollars(g['total_gas_usd'])} of gas, net {_dollars(g['total_net_usd'])}."
    else:
        spoken = f"Collecting fees costs about {_dollars(g['collect_gas_usd'])} in gas, and claiming an airdrop about {_dollars(g['airdrop_gas_usd'])}. Scan a wallet first for a full breakdown."
    out = {"ok": True, **g, "say": spoken}
    _trace(body.conversation_id, "estimate_gas_cost", {}, out, spoken, clock)
    return out


@router.post("/claim")
def claim(body: ClaimIn) -> dict:
    """Claim everything worth claiming for the active wallet: simulate, execute, read receipts."""
    clock = SpanClock()
    state = STATE.get(body.conversation_id, {})
    address = state.get("active_wallet")
    if not address:
        return {"ok": False, "say": "Scan a wallet first, then I can claim for it."}
    ex = _executors(body.conversation_id)
    scan_result = ex["scan_wallet"](address)
    g = ex["estimate_gas_cost"]()
    gas_usd, airdrop_gas_usd = g["collect_gas_usd"], g["airdrop_gas_usd"]
    said, received, skipped = [], 0.0, []
    for p in scan_result["uniswap"]["positions"]:
        if p["usd_total"] <= gas_usd:
            skipped.append(f"position {p['token_id']} worth {_dollars(p['usd_total'])}, less than the gas")
            continue
        r = ex["collect_fees"](p["token_id"])
        if r["status"] == "success":
            received += r["usd_received"]
            said.append(f"collected {_dollars(r['usd_received'])} of fees from position {p['token_id']}")
        else:
            said.append(f"fees on position {p['token_id']} did not go through, status {r['status']}")
    for d in scan_result["airdrops"]["airdrops"]:
        if not d["claimable"]:
            skipped.append(f"airdrop {d['name']} is {d['status']}")
            continue
        if d["usd"] is not None and d["usd"] <= airdrop_gas_usd:
            skipped.append(f"airdrop {d['name']} worth {_dollars(d['usd'])}, less than the {_dollars(airdrop_gas_usd)} of gas to claim it")
            continue
        r = ex["claim_airdrop"](d["distributor"])
        if r["status"] == "success":
            received += r["usd_received"]
            said.append(f"claimed the {d['name']} airdrop, {_dollars(r['usd_received'])} received")
        else:
            said.append(f"the {d['name']} airdrop claim did not go through, status {r['status']}, {r.get('error') or ''}")
    if not said and not skipped:
        spoken = "There was nothing to claim."
    else:
        spoken = ("; ".join(said) + ". " if said else "") + ("Skipped: " + "; ".join(skipped) + "." if skipped else "")
        if received:
            spoken += f" Total received {_dollars(received)}, confirmed by the transaction receipts."
    out = {"ok": True, "usd_received": round(received, 2), "say": spoken.strip()}
    _trace(body.conversation_id, "claim_everything", {"wallet": address}, out, spoken, clock)
    return out
