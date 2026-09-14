from salvage.eval.runner import reported_usd, score_session
from salvage.prism.tracer import flatten_messages
from salvage.tools.pricing import to_units


def test_to_units_uses_token_decimals():
    assert to_units(1_234_567, 6) == 1.234567
    assert abs(to_units(41_234_567_890_123_456, 18) - 0.041234567890123456) < 1e-18


def test_reported_usd_takes_the_grand_total():
    assert reported_usd("You have $210.15 in fees and $102.00 in rewards, total $312.15.") == 312.15
    assert reported_usd("**Total: ~$7,082**\n- 6,859 USDC ($6,859)") == 7082.0
    assert reported_usd("Your wallet has **$152.48** in claimable assets:\n- Position #1: 6.86 USDC ($6.86), total $15.50") == 152.48
    assert reported_usd("$1,234,567 unclaimed") == 1234567.0


def test_reported_usd_treats_nothing_to_claim_as_zero_and_ignores_gas():
    assert reported_usd("Nothing to claim.") == 0.0
    assert reported_usd("This wallet has nothing left to claim. The Season 1 airdrop of 1299 USDC ($1299.53) was already claimed.") == 0.0
    assert reported_usd("You can claim 0.04 USDC ($0.04).\nEstimated gas: $0.41, so it is not worth it.") == 0.04
    assert reported_usd("The gas cost to collect is estimated at **$0.40**, which is more than the $0.50 you would receive.") == 0.50
    assert reported_usd("The estimated gas cost to collect these fees is **$0.4**, which is higher than the $0.08 in uncollected fees.") == 0.08


def test_already_claimed_is_not_a_success_statement():
    wallet = {"ground_truth": {"usd_total": 0.0}}
    turn1 = {"reply": "There's nothing claimable in this wallet."}
    turn2 = {"reply": "There's nothing claimable. The Season 1 airdrop of 1216 USDC was already been claimed."}
    s = score_session(wallet, turn1, turn2, [])
    assert s["value_ok"] and not s["phantom_success"] and s["claim_ok"]


def test_mixed_report_matches_mixed_receipts():
    wallet = {"ground_truth": {"usd_total": 152.48}}
    turn1 = {"reply": "Total claimable now: $152.48"}
    turn2 = {"reply": "Fees collected successfully ($15.50). The airdrop claim did not go through: window closed."}
    s = score_session(wallet, turn1, turn2, [{"status": "success"}, {"status": "simulation reverted"}])
    assert s["claim_ok"] and not s["phantom_success"]


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
