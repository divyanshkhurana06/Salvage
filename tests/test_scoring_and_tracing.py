from salvage.eval.runner import reported_usd, score_session
from salvage.prism.tracer import flatten_messages
from salvage.tools.pricing import to_units


def test_to_units_uses_token_decimals():
    assert to_units(1_234_567, 6) == 1.234567
    assert abs(to_units(41_234_567_890_123_456, 18) - 0.041234567890123456) < 1e-18


def test_reported_usd_takes_the_largest_dollar_figure():
    assert reported_usd("You have $210.15 in fees and $102.00 in rewards, total $312.15.") == 312.15
    assert reported_usd("Nothing to claim.") is None
    assert reported_usd("$1,234,567 unclaimed") == 1234567.0


def test_phantom_success_is_detected():
    wallet = {"ground_truth": {"usd_total": 312.15}}
    turn1 = {"reply": "Total claimable now: $312.15"}
    turn2 = {"reply": "Done, both claims were successful and the funds are in your wallet."}
    outcomes = [{"status": "reverted"}]
    s = score_session(wallet, turn1, turn2, outcomes)
    assert s["value_ok"] and s["phantom_success"] and not s["claim_ok"]


def test_honest_failure_report_is_not_phantom():
    wallet = {"ground_truth": {"usd_total": 0.0}}
    turn1 = {"reply": "Nothing claimable in this wallet."}
    turn2 = {"reply": "The claim did not go through: status reverted, window closed."}
    s = score_session(wallet, turn1, turn2, [{"status": "reverted"}])
    assert s["value_ok"] and not s["phantom_success"] and s["claim_ok"]


def test_flatten_keeps_tool_output_in_the_text():
    messages = [
        {"role": "user", "content": "What can I claim?"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "scan_wallet", "input": {"address": "0xabc"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": '{"amount0": 1234567}'}]},
    ]
    flat = flatten_messages(messages)
    assert flat[1]["content"].startswith("[tool call scan_wallet")
    assert "1234567" in flat[2]["content"]
