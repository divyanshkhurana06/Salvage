# Salvage

An AI agent that finds money a crypto wallet is owed but has never collected, and claims it, with every number verified against the chain before it is shown. Built for the ForgeAI Reliability Hackathon at graVITas 2026 (VIT Vellore), Track: AI for Finance. Team Ingenious.

Salvage ships in two versions on purpose. **v1** is the naive first draft any team would write. **v2** is the same agent with the fixes. PRISM (by Block Convey) records both, shows exactly where v1 goes wrong, and proves that v2 does not, on the same set of wallets.

## What it does

You paste a wallet address. Salvage scans it on a local fork of Ethereum mainnet for:

* uncollected Uniswap v3 LP fees (real positions, real contracts, real prices from Chainlink)
* unclaimed airdrops (merkle distributor contracts with published eligibility lists)

It tells you what is claimable and what it is worth in dollars, and when you ask, it claims it and shows you the receipt. You can talk to it: "only the Uniswap one", "is the gas worth it?", "now check my other wallet".

Everything runs against an Anvil fork of mainnet, so the contracts, positions, and prices are real, but no real funds move. Claims execute by impersonating the wallet on the fork, which is how you can watch exactly what a claim would do before doing it for real.

## The failure nobody planted

v1 reads what the contracts return and writes the answer itself. That is enough to break it:

* **Decimals.** USDC has 6 decimals. The contract returns `1234567`; v1 reports "$1,234,567". The real figure is $1.23.
* **Success from memory.** v1 sends a claim and returns the transaction hash. It never reads the receipt. A reverted claim and a successful one look identical, so it says "claimed" either way.
* **Stale state.** v1 keeps everything it has seen in one conversation. Switch wallets and it can answer about the old one.

None of this needs an attacker. It is what an agent does when it is trusted to interpret raw numbers and remember state.

## The fix

v2 changes the architecture, not the prompt:

* amounts are converted and priced in code, never by the model
* every claim is simulate, execute, read the receipt; the reply is generated from the receipt
* the agent scans again before acting, and switching wallets resets the conversation state
* "nothing to claim" is a first class answer, so users are never pushed into claims that cost more in gas than they return

## How PRISM is used

Every agent turn sends three records to PRISM, all tied together by one session id per conversation:

1. a trace: the user message, the reply, model, latency, tokens, and metadata (wallet, cohort, version)
2. spans: one per model call and one per tool call, with the tool input and output visible
3. a trajectory: the ordered steps of the run

That is how the raw number the tool returned and the number the agent reported end up side by side in one PRISM trace. Failure clustering across the wallet set names the patterns; the same wallet set is replayed against v2 to prove the improvement. See `GUIDE.md` for the demo runbook.

## Quick start

Prerequisites: Python 3.11 or newer, [Foundry](https://getfoundry.sh) (for `anvil` and `forge`), an Anthropic API key, and a PRISM API key from prism.blockconvey.com.

```bash
git clone https://github.com/divyanshkhurana06/Salvage.git
cd Salvage
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then fill in ANTHROPIC_API_KEY, MODEL_ID, PRISMTRACE_API_KEY
```

Start the fork, find real positions, and build the wallet set:

```bash
scripts/start_fork.sh background            # Anvil fork of mainnet at the pinned block
(cd contracts && forge build)               # compiles the airdrop distributor
.venv/bin/python scripts/probe_positions.py 30          # finds real Uniswap positions with collectable fees
.venv/bin/python scripts/build_test_set.py              # deploys airdrops, writes data/wallets.json with ground truth
.venv/bin/python -m salvage.cli doctor                  # fork, model, and PRISM status
```

Talk to it, or run the web UI:

```bash
.venv/bin/python -m salvage.cli chat v2
.venv/bin/python -m salvage.cli serve 8000              # then open http://127.0.0.1:8000
```

Run the evaluation and print the before and after table:

```bash
.venv/bin/python -m salvage.cli eval v1
.venv/bin/python -m salvage.cli eval v2
.venv/bin/python -m salvage.cli report
```

The fork keeps its state only while it runs. After restarting it, run `build_test_set.py` again.

## Project layout

```
salvage/
  chain.py            web3 connection to the fork, impersonation, snapshots
  contracts.py        mainnet addresses and minimal ABIs
  tools/
    uniswap.py        positions and collectable fees (raw for v1, verified for v2)
    airdrops.py       merkle tree, registry, eligibility and claim status
    pricing.py        Chainlink USD prices
    claims.py         naive claims (hash only) and verified claims (simulate, execute, receipt)
  agent/
    prompts.py        the v1 and v2 system prompts
    tools_schema.py   tool definitions the model sees, and the executors behind them
    loop.py           the tool calling loop, one turn in, one traced turn out
    llm.py            model access, plus a scripted model for tests
  prism/tracer.py     traces, spans, and trajectories to PRISM (offline log when no key)
  eval/
    runner.py         runs the wallet set, scores replies against the chain
    report.py         before and after table
  server.py           FastAPI backend for the UI
  cli.py              command line entry points
contracts/            the MerkleAirdrop distributor (Solidity, Foundry)
scripts/              start_fork.sh, probe_positions.py, build_test_set.py
ui/index.html         the demo UI
tests/                unit tests (no network, no keys)
data/                 candidates, airdrop registry, wallet set, run outputs
```

## What is real and what is not

* The Uniswap positions, their fees, the token contracts, and the Chainlink prices are the real mainnet state at the pinned block.
* The airdrop distributors are deployed by `build_test_set.py` on the fork, funded with real USDC from a large holder on the fork, so that some wallets have an airdrop to claim, some already claimed it, and some missed the window. A real airdrop plugs into the same registry format.
* Claims are real transactions on the fork, signed by impersonating the wallet. On mainnet the user would sign them.
* The evaluation scores against the chain, not against the model: a reported value is correct if it is within 5 percent of what the verified tools compute, and a claim report is correct if it matches the transaction receipts.

## Tests

```bash
.venv/bin/python -m pytest
```

The tests cover the merkle tree against the Solidity encoding, unit conversion, the scoring rules, trace flattening, and the agent loop with a scripted model and fake tools. They need no network and no keys.
