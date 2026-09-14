"""Model access. One real backend (the Anthropic Messages API) and one scripted backend for tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..config import settings


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class ModelReply:
    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
    tokens_in: int = 0
    tokens_out: int = 0
    raw_content: list[dict] = field(default_factory=list)


class LLM:
    """Interface the agent loop talks to."""

    model_id: str = "scripted"

    def complete(self, system: str, messages: list[dict], tools: list[dict]) -> ModelReply:  # pragma: no cover
        raise NotImplementedError


class AnthropicLLM(LLM):
    def __init__(self, model_id: str | None = None, max_tokens: int = 1200):
        import anthropic

        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.model_id = model_id or settings.model_id
        if not self.model_id:
            raise RuntimeError("MODEL_ID is not set")
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.max_tokens = max_tokens

    def complete(self, system: str, messages: list[dict], tools: list[dict]) -> ModelReply:
        import time

        import anthropic

        # the SDK retries quickly on its own; this outer loop rides out longer network blips
        delays = [5, 15, 30]
        for attempt in range(len(delays) + 1):
            try:
                resp = self.client.messages.create(
                    model=self.model_id, max_tokens=self.max_tokens, system=system, messages=messages, tools=tools,
                )
                break
            except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError) as exc:
                if attempt == len(delays):
                    raise
                print(f"[model] {type(exc).__name__}, retrying in {delays[attempt]}s")
                time.sleep(delays[attempt])
        text_parts, calls, raw = [], [], []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
                raw.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, input=dict(block.input)))
                raw.append({"type": "tool_use", "id": block.id, "name": block.name, "input": dict(block.input)})
        return ModelReply(
            text="\n".join(text_parts).strip(), tool_calls=calls, stop_reason=resp.stop_reason or "",
            tokens_in=getattr(resp.usage, "input_tokens", 0), tokens_out=getattr(resp.usage, "output_tokens", 0),
            raw_content=raw,
        )


class ScriptedLLM(LLM):
    """A deterministic stand in for tests: a function decides the next reply from the conversation."""

    model_id = "scripted"

    def __init__(self, script: Callable[[list[dict], list[dict]], ModelReply]):
        self.script = script
        self.calls = 0

    def complete(self, system: str, messages: list[dict], tools: list[dict]) -> ModelReply:
        self.calls += 1
        return self.script(messages, tools)


def make_llm() -> LLM:
    return AnthropicLLM()


def tool_use_block(call: ToolCall) -> dict:
    return {"type": "tool_use", "id": call.id, "name": call.name, "input": call.input}


def tool_result_block(call_id: str, content: Any, is_error: bool = False) -> dict:
    import json

    text = content if isinstance(content, str) else json.dumps(content, default=str)
    block = {"type": "tool_result", "tool_use_id": call_id, "content": text}
    if is_error:
        block["is_error"] = True
    return block
