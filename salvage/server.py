"""Web UI backend: chat with either agent version, see every tool call, reset the fork between demos."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .agent.loop import Agent
from .chain import available_chains, get_chain
from .config import DATA_DIR, ROOT, settings
from .eval.report import compare
from .eval.runner import latest_run

from .voice import router as voice_router

app = FastAPI(title="Salvage")
app.include_router(voice_router)
SESSIONS: dict[str, Agent] = {}
BASE_SNAPSHOT: dict[str, str] = {}  # chain name -> snapshot id taken at startup, what Reset fork goes back to
UI_FILE = ROOT / "ui" / "index.html"


class NewSession(BaseModel):
    version: str = "v2"
    user_id: str = "demo"


class ChatIn(BaseModel):
    session_id: str
    message: str


@app.middleware("http")
async def require_access_code(request: Request, call_next):
    """When ACCESS_CODE is set (a public deployment), every call that spends model credits or moves the fork needs it.
    The page, the status, the wallet list and the voice tool endpoints stay open; the UI asks for the code once."""
    path = request.url.path
    guarded = path.startswith("/api/") and not path.startswith("/api/voice/") and path not in ("/api/status", "/api/wallets", "/api/report")
    if settings.access_code and guarded and request.headers.get("x-access-code", "") != settings.access_code:
        return JSONResponse({"detail": "access code required"}, status_code=401)
    return await call_next(request)


@app.on_event("startup")
def take_base_snapshot() -> None:
    try:
        for chain in available_chains():
            BASE_SNAPSHOT[chain.name] = chain.snapshot()
    except Exception:
        BASE_SNAPSHOT.clear()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return UI_FILE.read_text()


@app.get("/api/status")
def status() -> dict:
    # the wallet set records the block each fork was at when it was built; any block after that is a transaction mined since
    path = DATA_DIR / "wallets.json"
    built = json.loads(path.read_text()) if path.exists() else {}
    built_blocks = built.get("blocks") or ({"ethereum": built["block"]} if built.get("block") else {})
    forks = {}
    try:
        for chain in available_chains():
            block = chain.block_number
            built_at = built_blocks.get(chain.name)
            forks[chain.name] = {"ok": True, "label": chain.label, "block": block, "built_at": built_at,
                                 "txs_since_build": max(0, block - built_at) if built_at else None}
    except Exception as exc:
        forks["ethereum"] = {"ok": False, "label": "Ethereum", "error": str(exc)}
    return {"fork": forks.get("ethereum"), "forks": forks, "model": settings.llm_enabled, "prism": settings.prism_enabled,
            "prism_project": settings.prism_project_id, "voice_agent_id": settings.elevenlabs_agent_id,
            "access_code_required": bool(settings.access_code)}


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
    check = turn.get("check")
    return {"reply": turn["reply"], "tool_calls": turn["tool_calls"], "trace_id": turn["trace_id"],
            "latency_ms": turn["latency_ms"], "active_wallet": agent.active_wallet, "session_id": agent.session_id,
            "check": None if check is None else {k: check[k] for k in ("kind", "ok", "text") if k in check}}


class CheckIn(BaseModel):
    session_id: str


@app.post("/api/check")
def check_against_chain(body: CheckIn) -> dict:
    """The chain's verdict on the last turn of a session (already computed when the turn ran)."""
    agent = SESSIONS.get(body.session_id)
    if agent is None:
        raise HTTPException(404, "unknown session")
    check = agent.turns[-1].get("check") if agent.turns else None
    if check is None:
        return {"available": False}
    return {"available": True, **{k: v for k, v in check.items() if k not in ("start_time", "end_time", "duration_ms")}}


class ShockIn(BaseModel):
    factor: float = 0.6  # 0.6 means ETH and BTC lose 40 percent


@app.post("/api/shock")
def market_shock(body: ShockIn) -> dict:
    """Simulated black swan: ETH and BTC prices move by the factor for every scan from now on, on every chain.
    The naive agent keeps answering from what it read before the move; the verified agent scans again."""
    from .contracts import SHOCK_SYMBOLS
    from .tools import pricing

    if body.factor == 1.0:
        pricing.SHOCK.clear()
    else:
        for sym in SHOCK_SYMBOLS:
            pricing.SHOCK[sym] = body.factor
    return {"ok": True, "factor": body.factor, "active": bool(pricing.SHOCK)}


@app.post("/api/reset_fork")
def reset_fork() -> dict:
    """Every fork goes back to the state it had when the server started: claims undone, prices restored."""
    from .tools import pricing

    pricing.SHOCK.clear()
    blocks = {}
    for chain in available_chains():
        if chain.name in BASE_SNAPSHOT:
            chain.revert(BASE_SNAPSHOT[chain.name])
        BASE_SNAPSHOT[chain.name] = chain.snapshot()
        blocks[chain.name] = chain.block_number
    SESSIONS.clear()
    return {"ok": True, "block": blocks.get("ethereum"), "blocks": blocks}


@app.get("/api/report")
def report() -> dict:
    out = {"table": compare()}
    for v in ("v1", "v2"):
        p = latest_run(v)
        out[v] = json.loads(Path(p).read_text())["summary"] if p else None
    return JSONResponse(out)
