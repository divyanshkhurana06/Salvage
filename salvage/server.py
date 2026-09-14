"""Web UI backend: chat with either agent version, see every tool call, reset the fork between demos."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .agent.loop import Agent
from .chain import get_chain
from .config import DATA_DIR, ROOT, settings
from .eval.report import compare
from .eval.runner import latest_run

from .voice import router as voice_router

app = FastAPI(title="Salvage")
app.include_router(voice_router)
SESSIONS: dict[str, Agent] = {}
BASE_SNAPSHOT: dict[str, str | None] = {"id": None}
UI_FILE = ROOT / "ui" / "index.html"


class NewSession(BaseModel):
    version: str = "v2"
    user_id: str = "demo"


class ChatIn(BaseModel):
    session_id: str
    message: str


@app.on_event("startup")
def take_base_snapshot() -> None:
    try:
        BASE_SNAPSHOT["id"] = get_chain().snapshot()
    except Exception:
        BASE_SNAPSHOT["id"] = None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return UI_FILE.read_text()


@app.get("/api/status")
def status() -> dict:
    try:
        chain = get_chain()
        fork = {"ok": True, "block": chain.block_number}
    except Exception as exc:
        fork = {"ok": False, "error": str(exc)}
    return {"fork": fork, "model": settings.llm_enabled, "prism": settings.prism_enabled, "prism_project": settings.prism_project_id,
            "voice_agent_id": settings.elevenlabs_agent_id}


@app.get("/api/wallets")
def wallets() -> list[dict]:
    path = DATA_DIR / "wallets.json"
    if not path.exists():
        return []
    ws = json.loads(path.read_text())["wallets"]
    return [{"label": w["label"], "address": w["address"], "cohort": w["cohort"], "truth_usd": w["ground_truth"]["usd_total"]} for w in ws]


@app.post("/api/session")
def new_session(body: NewSession) -> dict:
    if body.version not in ("v1", "v2"):
        raise HTTPException(400, "version must be v1 or v2")
    session_id = f"{body.version}_ui_{uuid.uuid4().hex[:8]}"
    SESSIONS[session_id] = Agent(body.version, session_id=session_id, user_id=body.user_id, metadata={"source": "ui"})
    return {"session_id": session_id, "version": body.version}


@app.post("/api/chat")
def chat(body: ChatIn) -> dict:
    agent = SESSIONS.get(body.session_id)
    if agent is None:
        raise HTTPException(404, "unknown session, create one first")
    turn = agent.chat(body.message)
    return {"reply": turn["reply"], "tool_calls": turn["tool_calls"], "trace_id": turn["trace_id"],
            "latency_ms": turn["latency_ms"], "active_wallet": agent.active_wallet, "session_id": agent.session_id}


class CheckIn(BaseModel):
    session_id: str


@app.post("/api/check")
def check_against_chain(body: CheckIn) -> dict:
    """Compare what the agent just said with what the verified tools compute for the active wallet."""
    from .eval.runner import reported_usd
    from .tools import airdrops, uniswap

    agent = SESSIONS.get(body.session_id)
    if agent is None:
        raise HTTPException(404, "unknown session")
    wallet = agent.active_wallet
    if not wallet or not agent.turns:
        return {"available": False}
    fees = uniswap.scan_fees(wallet)
    drops = airdrops.scan_airdrops(wallet)
    truth = round(fees["usd_total"] + drops["usd_total"], 2)
    reported = reported_usd(agent.turns[-1]["reply"])
    ok = (reported is None or reported < 1.0) if truth == 0 else (reported is not None and abs(reported - truth) / truth <= 0.05)
    return {"available": True, "wallet": wallet, "truth_usd": truth, "reported_usd": reported, "ok": ok,
            "positions_scanned": fees["positions_scanned"], "positions_total": fees["positions_total"]}


class ShockIn(BaseModel):
    factor: float = 0.6  # 0.6 means ETH and BTC lose 40 percent


@app.post("/api/shock")
def market_shock(body: ShockIn) -> dict:
    """Simulated black swan: ETH and BTC prices move by the factor for every scan from now on.
    The naive agent keeps answering from what it read before the move; the verified agent scans again."""
    from .contracts import PRICED_TOKENS
    from .tools import pricing

    if body.factor == 1.0:
        pricing.SHOCK.clear()
    else:
        for sym in ("WETH", "WBTC"):
            pricing.SHOCK[PRICED_TOKENS[sym][0].lower()] = body.factor
    return {"ok": True, "factor": body.factor, "active": bool(pricing.SHOCK)}


@app.post("/api/reset_fork")
def reset_fork() -> dict:
    from .tools import pricing

    pricing.SHOCK.clear()
    chain = get_chain()
    if BASE_SNAPSHOT["id"] is not None:
        chain.revert(BASE_SNAPSHOT["id"])
    BASE_SNAPSHOT["id"] = chain.snapshot()
    SESSIONS.clear()
    return {"ok": True, "block": chain.block_number}


@app.get("/api/report")
def report() -> dict:
    out = {"table": compare()}
    for v in ("v1", "v2"):
        p = latest_run(v)
        out[v] = json.loads(Path(p).read_text())["summary"] if p else None
    return JSONResponse(out)
