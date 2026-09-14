"""Send every agent turn to PRISM.

One turn produces three records, all tied together by trace_id and session_id:

  1. a trace      (POST /api/traces)          the user message, the reply, model, latency, tokens, metadata
  2. its spans    (POST /api/spans/ingest)    one span per model call and per tool call, with tool input and output
  3. a trajectory (POST /api/trajectories)    the ordered steps of the run, for PRISM's trajectory evaluation

When no PRISM key is configured, nothing is sent and every record is still appended to
data/runs/prism_offline.jsonl so the run can be inspected locally.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from ..config import RUNS_DIR, settings

OFFLINE_LOG = RUNS_DIR / "prism_offline.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short(value: Any, limit: int = 4000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


@dataclass
class Span:
    name: str
    span_type: str  # "llm" or "tool"
    input_text: str
    output_text: str
    start_time: str
    end_time: str
    duration_ms: float
    status: str = "ok"
    error_message: str | None = None
    model: str | None = None
    token_count_input: int = 0
    token_count_output: int = 0
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_payload(self, parent_span_id: str) -> dict:
        out = {
            "span_id": self.span_id, "parent_span_id": parent_span_id, "name": self.name,
            "span_type": self.span_type, "input_text": self.input_text, "output_text": self.output_text,
            "start_time": self.start_time, "end_time": self.end_time, "duration_ms": int(self.duration_ms),
            "status": self.status,
        }
        if self.error_message:
            out["error_message"] = self.error_message
        if self.model:
            out["model"] = self.model
            out["token_count_input"] = self.token_count_input
            out["token_count_output"] = self.token_count_output
        return out


class SpanClock:
    """Small helper the agent loop uses to time a span."""

    def __init__(self):
        self.start_iso = _now_iso()
        self.t0 = time.perf_counter()

    def finish(self) -> tuple[str, float]:
        return _now_iso(), (time.perf_counter() - self.t0) * 1000


def flatten_messages(messages: list[dict]) -> list[dict]:
    """Turn API style messages (with tool_use and tool_result blocks) into plain text messages.

    Tool outputs are kept in the text on purpose: that is how the raw numbers the agent saw
    end up next to the numbers it reported, inside one PRISM trace.
    """
    flat = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            flat.append({"role": m["role"], "content": content})
            continue
        parts = []
        for block in content or []:
            btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
            if btype == "text":
                parts.append(block.get("text") if isinstance(block, dict) else block.text)
            elif btype == "tool_use":
                name = block.get("name") if isinstance(block, dict) else block.name
                args = block.get("input") if isinstance(block, dict) else block.input
                parts.append(f"[tool call {name} {_short(args, 800)}]")
            elif btype == "tool_result":
                inner = block.get("content") if isinstance(block, dict) else block.content
                parts.append(f"[tool result {_short(inner, 2500)}]")
        flat.append({"role": m["role"], "content": "\n".join(p for p in parts if p)})
    return flat


class Tracer:
    def __init__(self, enabled: bool | None = None):
        self.enabled = settings.prism_enabled if enabled is None else enabled
        self.host = settings.prism_host
        self.project_id = settings.prism_project_id
        self._pt = None
        self._http: httpx.Client | None = None
        if self.enabled:
            from prismtrace import PRISMtrace  # imported lazily so offline runs need nothing

            self._pt = PRISMtrace(api_key=settings.prism_api_key, host=self.host, project_id=self.project_id)
            self._http = httpx.Client(
                base_url=self.host, timeout=20,
                headers={"X-PRISMtrace-Key": settings.prism_api_key, "Content-Type": "application/json"},
            )
        RUNS_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- diagnostics ----------
    def doctor(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "reason": "PRISMTRACE_API_KEY or PRISMTRACE_PROJECT_ID missing"}
        out: dict[str, Any] = {"enabled": True, "host": self.host, "project_id": self.project_id}
        r = self._http.post("/api/setup-doctor/handshake", json={"project_id": self.project_id, "send_test_trace": False})
        out["handshake_status"] = r.status_code
        out["handshake"] = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:300]
        r2 = self._http.get("/api/setup-doctor", params={"project_id": self.project_id})
        out["setup_doctor_status"] = r2.status_code
        out["setup_doctor"] = r2.json() if r2.headers.get("content-type", "").startswith("application/json") else r2.text[:300]
        return out

    # ---------- recording ----------
    def record_turn(
        self,
        *,
        session_id: str,
        agent_id: str,
        agent_name: str,
        model: str,
        input_messages: list[dict],
        output_text: str,
        latency_ms: int,
        spans: list[Span],
        metadata: dict,
        tokens_in: int = 0,
        tokens_out: int = 0,
        final_status: str = "success",
    ) -> str:
        trace_id = str(uuid.uuid4())
        root_span_id = str(uuid.uuid4())
        flat_inputs = flatten_messages(input_messages)
        meta = {**metadata, "session_id": session_id}

        record = {
            "trace_id": trace_id, "session_id": session_id, "agent_id": agent_id, "model": model,
            "latency_ms": latency_ms, "input_messages": flat_inputs, "output_message": output_text,
            "spans": [s.to_payload(root_span_id) for s in spans], "metadata": meta, "sent": self.enabled,
            "recorded_at": _now_iso(),
        }
        with OFFLINE_LOG.open("a") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

        if not self.enabled:
            return trace_id

        self._pt.trace_llm(
            model=model, input_messages=flat_inputs, output=output_text, latency_ms=latency_ms,
            token_count_input=tokens_in, token_count_output=tokens_out, trace_id=trace_id,
            agent_id=agent_id, agent_name=agent_name, session_id=session_id, metadata=meta,
        )
        # the SDK posts on a background thread; wait for it so the trace exists before its spans
        # arrive under the same trace_id, otherwise the two inserts can collide
        self._pt.flush(timeout=15)

        span_payload = {
            "trace_id": trace_id, "project_id": self.project_id, "session_id": session_id,
            "metadata": {"agent_id": agent_id, "agent_name": agent_name},
            "spans": [{
                "span_id": root_span_id, "name": f"turn:{agent_name}", "span_type": "agent",
                "input_text": _short(flat_inputs[-1]["content"] if flat_inputs else ""),
                "output_text": _short(output_text), "start_time": spans[0].start_time if spans else _now_iso(),
                "end_time": spans[-1].end_time if spans else _now_iso(), "duration_ms": latency_ms, "status": "ok",
            }] + [s.to_payload(root_span_id) for s in spans],
        }
        try:
            r = self._http.post("/api/spans/ingest", json=span_payload)
            if r.status_code >= 300:
                print(f"[prism] spans ingest {r.status_code}: {r.text[:200]}")
        except Exception as exc:
            print(f"[prism] spans ingest failed: {exc}")

        steps = []
        for s in spans:
            if s.span_type == "llm":
                steps.append({"step_type": "reasoning", "label": s.name, "input_summary": s.input_text[:200],
                              "output_summary": s.output_text[:200], "duration_ms": int(s.duration_ms),
                              "token_count": int(s.token_count_input + s.token_count_output), "status": "success" if s.status == "ok" else "error"})
            else:
                steps.append({"step_type": "tool_call", "label": s.name, "tool_name": s.name.replace("tool:", ""),
                              "input_summary": s.input_text[:200], "output_summary": s.output_text[:200],
                              "duration_ms": int(s.duration_ms), "status": "success" if s.status == "ok" else "error"})
        steps.append({"step_type": "final_answer", "label": "reply", "output_summary": output_text[:200], "duration_ms": 0})
        try:
            self._pt.submit_trajectory(steps, agent_name=agent_name, agent_id=agent_id, conversation_id=session_id,
                                       request_id=trace_id, model=model, final_status=final_status)
        except Exception as exc:
            print(f"[prism] trajectory failed: {exc}")
        return trace_id

    def close(self) -> None:
        if self._pt is not None:
            try:
                self._pt.flush()
                self._pt.close()
            except Exception:
                pass
        if self._http is not None:
            self._http.close()


_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer
