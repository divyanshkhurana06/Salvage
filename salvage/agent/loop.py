"""The agent loop: one user turn in, tool calls in the middle, one reply out, everything traced."""

from __future__ import annotations

import json
import time
import uuid
from typing import Callable

from ..prism.tracer import Span, SpanClock, Tracer, get_tracer
from .llm import LLM, ModelReply, make_llm, tool_result_block, tool_use_block
from .prompts import V1_SYSTEM, V2_SYSTEM
from .tools_schema import Executors, tools_for

MAX_ITERATIONS = 8


class Agent:
    def __init__(
        self,
        version: str = "v2",
        *,
        llm: LLM | None = None,
        executors: dict[str, Callable] | None = None,
        tracer: Tracer | None = None,
        session_id: str | None = None,
        user_id: str = "demo",
        metadata: dict | None = None,
        chain=None,
    ):
        if version not in ("v1", "v2"):
            raise ValueError("version must be v1 or v2")
        self.version = version
        self.llm = llm or make_llm()
        self.tracer = tracer or get_tracer()
        self.session_id = session_id or f"{version}-{uuid.uuid4().hex[:8]}"
        self.user_id = user_id
        self.metadata = dict(metadata or {})
        self.state: dict = {"active_wallet": None}
        self.chain = chain
        if executors is None:
            from ..chain import get_chain

            self.chain = chain or get_chain()
            executors = Executors(version, self.chain, self.state).mapping()
        self.executors = executors
        self.tools = tools_for(version)
        self.system = V1_SYSTEM if version == "v1" else V2_SYSTEM
        self.messages: list[dict] = []
        self.turns: list[dict] = []
        self.agent_id = f"salvage_{version}"
        self.agent_name = f"Salvage {version}"

    # ---------- one user turn ----------
    def chat(self, user_text: str) -> dict:
        turn_start = len(self.messages)
        wallet_before = self.state.get("active_wallet")
        self.messages.append({"role": "user", "content": user_text})
        spans: list[Span] = []
        tool_calls: list[dict] = []
        t_turn = time.perf_counter()
        tokens_in = tokens_out = 0
        reply: ModelReply | None = None

        for _ in range(MAX_ITERATIONS):
            clock = SpanClock()
            reply = self.llm.complete(self.system, self.messages, self.tools)
            end, dur = clock.finish()
            tokens_in += reply.tokens_in
            tokens_out += reply.tokens_out
            spans.append(Span(
                name=f"llm:{self.llm.model_id}", span_type="llm", model=self.llm.model_id,
                input_text=self._last_user_or_tool_text(), output_text=reply.text or json.dumps(reply.raw_content, default=str)[:2000],
                start_time=clock.start_iso, end_time=end, duration_ms=dur,
                token_count_input=reply.tokens_in, token_count_output=reply.tokens_out,
            ))
            if not reply.tool_calls:
                break

            self.messages.append({"role": "assistant", "content": reply.raw_content or [tool_use_block(c) for c in reply.tool_calls]})
            results = []
            for call in reply.tool_calls:
                clock = SpanClock()
                result, is_error = self._execute(call.name, call.input)
                end, dur = clock.finish()
                spans.append(Span(
                    name=f"tool:{call.name}", span_type="tool",
                    input_text=json.dumps(call.input, default=str), output_text=json.dumps(result, default=str)[:6000],
                    start_time=clock.start_iso, end_time=end, duration_ms=dur,
                    status="error" if is_error else "ok", error_message=str(result)[:300] if is_error else None,
                ))
                tool_calls.append({"name": call.name, "input": call.input, "output": result, "error": is_error})
                results.append(tool_result_block(call.id, result, is_error))
            self.messages.append({"role": "user", "content": results})

        text = (reply.text if reply else "") or "(no reply)"
        self.messages.append({"role": "assistant", "content": text})
        latency_ms = int((time.perf_counter() - t_turn) * 1000)

        # v2 resets state when the conversation moves to a different wallet
        wallet_after = self.state.get("active_wallet")
        if self.version == "v2" and wallet_before and wallet_after and wallet_before != wallet_after:
            self.messages = self.messages[turn_start:]

        turn = {"user": user_text, "reply": text, "tool_calls": tool_calls, "latency_ms": latency_ms,
                "tokens_in": tokens_in, "tokens_out": tokens_out, "check": None}
        metadata = {**self.metadata, "agent_version": self.version, "user_identifier": self.user_id, "wallet": wallet_after or ""}

        # the chain's verdict on this turn travels with the trace: as metadata, and as a span in the timeline
        check = self._check(turn, wallet_after)
        if check is not None:
            turn["check"] = check
            metadata.update({"chain_check": "match" if check["ok"] else "mismatch", "chain_check_kind": check["kind"]})
            for key in ("truth_usd", "reported_usd", "usd_received"):
                if check.get(key) is not None:
                    metadata[key] = check[key]
            spans.append(Span(
                name="check:chain", span_type="tool", input_text=json.dumps({"kind": check["kind"], "wallet": wallet_after}),
                output_text=check["text"], start_time=check["start_time"], end_time=check["end_time"], duration_ms=check["duration_ms"],
                status="ok" if check["ok"] else "error", error_message=None if check["ok"] else check["text"][:300],
            ))

        turn["trace_id"] = self.tracer.record_turn(
            session_id=self.session_id, agent_id=self.agent_id, agent_name=self.agent_name, model=self.llm.model_id,
            input_messages=self.messages[:-1], output_text=text, latency_ms=latency_ms, spans=spans, metadata=metadata,
            tokens_in=tokens_in, tokens_out=tokens_out,
            final_status="error" if any(t["error"] for t in tool_calls) or (check is not None and not check["ok"]) else "success",
        )
        self.turns.append(turn)
        return turn

    def _check(self, turn: dict, wallet: str | None) -> dict | None:
        """Compare the reply with the chain. Only when the agent runs against a real fork; never breaks a turn."""
        if self.chain is None:
            return None
        from ..eval.check import check_turn

        clock = SpanClock()
        try:
            result = check_turn(turn, wallet, self.chain)
        except Exception as exc:
            print(f"[check] skipped: {exc}")
            return None
        if result is None:
            return None
        end, dur = clock.finish()
        return {**result, "start_time": clock.start_iso, "end_time": end, "duration_ms": dur}

    # ---------- helpers ----------
    def _execute(self, name: str, args: dict) -> tuple[object, bool]:
        fn = self.executors.get(name)
        if fn is None:
            return {"error": f"unknown tool {name}"}, True
        try:
            return fn(**args), False
        except Exception as exc:
            return {"error": str(exc)[:400]}, True

    def _last_user_or_tool_text(self) -> str:
        for m in reversed(self.messages):
            if m["role"] == "user":
                c = m["content"]
                if isinstance(c, str):
                    return c[:2000]
                return json.dumps(c, default=str)[:2000]
        return ""

    @property
    def active_wallet(self) -> str | None:
        return self.state.get("active_wallet")
