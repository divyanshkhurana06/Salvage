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

## Results

28 wallets, two turns each ("What can I claim in wallet X?" then "Claim everything that is worth claiming."), same wallets and same fork state for both versions. Scored against the chain, not against the model.

| Metric | v1 (naive) | v2 (verified) |
|---|---|---|
| Wallets scored | 28 | 28 |
| Reported value within 5% of the chain | 39.3% | 96.4% |
| Mean absolute error (USD) | $11,504,402.99 | $0.08 |
| Largest error (USD) | $302,999,691.86 | $2.19 |
| Phantom successes (said claimed, nothing succeeded) | 3 | 0 |
| Claim reports matching receipts | 89.3% | 100.0% |

| Cohort | v1 value ok | v2 value ok | v1 phantom | v2 phantom |
|---|---|---|---|---|
| airdrop | 4/6 | 6/6 | 0 | 0 |
| both (fees and airdrop) | 0/6 | 6/6 | 0 | 0 |
| fees | 0/6 | 5/6 | 0 | 0 |
| claimed_airdrop | 3/3 | 3/3 | 0 | 0 |
| expired_airdrop | 0/3 | 3/3 | 3 | 0 |
| empty | 4/4 | 4/4 | 0 | 0 |

Every session of both runs is in PRISM (agents `salvage_v1` and `salvage_v2`, one session per wallet, named like `v1_fees_08_<run id>`).

What v1 actually said on a wallet whose fees are worth $0.50 (the contract returned `210` for WBTC, which has 8 decimals, and `340229` for USDC, which has 6):

> WBTC 210 at $77,705.05 = $16,318,060.50. USDC 340,229 at $1.00 = $340,229.00. TOTAL $16,658,289.50. You have over $16.6 million in uncollected LP fees waiting for you!

And on a wallet whose airdrop window had closed, after its claim transaction reverted:

> Claimed! Season 0 rewards: 250,000 USDC (~$250,000 USD). Transaction: 0xe549cc51… Your USDC is now yours. Check your wallet to confirm the transfer!

v2 on the same wallets: "$0.50 in fees, the estimated gas cost is $0.40, borderline whether it is worth collecting", and "the claim did not go through: window closed". v2's one miss is a reply that stated the net after gas ($1.79) instead of the $2.19 it could claim.

Reproduce with `eval v1`, `eval v2`, `report`; `rescore` re-applies the scoring rules to saved runs without spending model calls.

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

Or bring everything up with one command (starts the fork if needed, compiles, builds the wallet set if the fork is fresh, runs the doctor, serves the UI):

```bash
scripts/demo.sh
```

The UI has three modes: v1, v2, and **side by side**, which sends the same message to both versions and shows the two replies next to each other with every tool call tagged by version. Under every reply a badge reports what the chain actually says for that wallet, so a wrong number is caught on screen. The **Results** button shows the measured before and after table from the latest evaluation runs. **Speak** turns the browser's speech recognition on for one message and **Read aloud** speaks the replies; both use the browser's own engines, nothing external.

Run the evaluation and print the before and after table:

```bash
.venv/bin/python -m salvage.cli eval v1
.venv/bin/python -m salvage.cli eval v2
.venv/bin/python -m salvage.cli report
```

The fork keeps its state only while it runs. After restarting it, run `build_test_set.py` again.

## Voice (optional)

Salvage can also be spoken to. An ElevenLabs voice agent runs the conversation and calls this server's `/api/voice` tools through a tunnel; the tools are the same verified v2 layer, keyed by the ElevenLabs conversation id, and every tool call is traced into PRISM under the agent `salvage_voice`. Wallets are referred to by short names in speech ("fees eight", "both one") because nobody can say a 40 character address.

```bash
.venv/bin/python scripts/tunnel.py 8000          # keeps running; writes the public url to data/public_url.txt
.venv/bin/python scripts/setup_voice.py          # creates or updates the ElevenLabs tools and agent, writes the id to .env
.venv/bin/python -m salvage.cli serve 8000       # the widget appears in the UI when ELEVENLABS_AGENT_ID is set
```

Needs `ELEVENLABS_API_KEY` and `NGROK_AUTHTOKEN` in `.env`. The tunnel url changes on every restart, so run `setup_voice.py` again after restarting the tunnel. To have PRISM record the full call transcript as well, point ElevenLabs' post call webhook at PRISM's ElevenLabs connector (see `GUIDE.md`).

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
