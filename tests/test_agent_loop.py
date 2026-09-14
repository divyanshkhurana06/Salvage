"""The agent loop with a scripted model and fake tools. No network, no fork, no keys."""

from salvage.agent.llm import ModelReply, ScriptedLLM, ToolCall
from salvage.agent.loop import Agent
from salvage.prism.tracer import Tracer


def fake_executors(state: dict):
    def scan(address: str):
        state["active_wallet"] = address
        return {"usd_total": 12.5, "summary": "Total claimable now: $12.50"}

    def collect(token_id: int):
        return {"status": "success", "usd_received": 12.5, "received": []}

    return {"scan_wallet": scan, "collect_fees": collect, "estimate_gas_cost": lambda: {"collect_gas_usd": 0.4, "airdrop_gas_usd": 0.2, "actions": []}, "claim_airdrop": lambda distributor: {"status": "reverted"}}


def script(messages, tools):
    last = messages[-1]["content"]
    if isinstance(last, str) and "wallet" in last:
        return ModelReply(text="", tool_calls=[ToolCall(id="c1", name="scan_wallet", input={"address": "0x" + "ab" * 20})], stop_reason="tool_use",
                          raw_content=[{"type": "tool_use", "id": "c1", "name": "scan_wallet", "input": {"address": "0x" + "ab" * 20}}])
    if isinstance(last, list) and last[0].get("tool_use_id") == "c1":
        return ModelReply(text="Total claimable now: $12.50", tool_calls=[], stop_reason="end_turn")
    if isinstance(last, str) and "laim" in last:
        return ModelReply(text="", tool_calls=[ToolCall(id="c2", name="collect_fees", input={"token_id": 1})], stop_reason="tool_use",
                          raw_content=[{"type": "tool_use", "id": "c2", "name": "collect_fees", "input": {"token_id": 1}}])
    return ModelReply(text="Collected, status success, $12.50 received.", tool_calls=[], stop_reason="end_turn")


def test_two_turns_with_tools_and_offline_tracing(tmp_path, monkeypatch):
    import salvage.prism.tracer as tracer_mod

    monkeypatch.setattr(tracer_mod, "OFFLINE_LOG", tmp_path / "offline.jsonl")
    tracer = Tracer(enabled=False)  # tests never talk to PRISM
    assert tracer.enabled is False

    state = {"active_wallet": None}
    agent = Agent("v2", llm=ScriptedLLM(script), executors=fake_executors(state), tracer=tracer, session_id="test_session")
    agent.state = state

    t1 = agent.chat("What can I claim in wallet 0xabab?")
    assert t1["reply"] == "Total claimable now: $12.50"
    assert [c["name"] for c in t1["tool_calls"]] == ["scan_wallet"]
    assert t1["trace_id"]

    t2 = agent.chat("Claim everything that is worth claiming.")
    assert t2["tool_calls"][0]["name"] == "collect_fees"
    assert t2["tool_calls"][0]["output"]["status"] == "success"

    lines = (tmp_path / "offline.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    assert '"tool:scan_wallet"' in lines[0] and '"tool:collect_fees"' in lines[1]


def test_unknown_tool_is_reported_as_error_not_crash():
    def script_bad(messages, tools):
        if isinstance(messages[-1]["content"], str):
            return ModelReply(text="", tool_calls=[ToolCall(id="x", name="nope", input={})], stop_reason="tool_use",
                              raw_content=[{"type": "tool_use", "id": "x", "name": "nope", "input": {}}])
        return ModelReply(text="I could not do that.", tool_calls=[], stop_reason="end_turn")

    agent = Agent("v1", llm=ScriptedLLM(script_bad), executors={}, tracer=Tracer(enabled=False), session_id="test_err")
    t = agent.chat("hi")
    assert t["tool_calls"][0]["error"] is True
    assert t["reply"] == "I could not do that."
