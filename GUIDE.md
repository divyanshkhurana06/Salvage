# Salvage, explained

This is the plain language version of the project: what every piece does, why it is built that way, what happens when you run it, and how to demo it. Read this before the pitch.

## The one paragraph version

People leave money sitting in DeFi contracts: LP fees that have to be collected by hand, airdrops they never claimed. Salvage is an AI agent you give a wallet address to. It finds that money, prices it, and claims it. The catch, and the point of the project, is that the obvious way to build such an agent gets the numbers wrong: it reads raw contract output and reports "$1.2 million" when the real figure is $1.23, and it says "claimed" when the transaction actually reverted. We build that naive version first (v1), record it with PRISM, show the failures, then ship the fixed version (v2) and prove the fix on the same wallets.

## The moving parts

### The fork

We do not touch mainnet. `scripts/start_fork.sh` starts Anvil (part of Foundry) as a copy of Ethereum mainnet at one pinned block. Every contract and every balance is real as of that block, but the chain is local, so we can:

* read any position and any price exactly as they were
* impersonate any wallet and send transactions as it (Anvil allows this with `anvil_impersonateAccount`)
* take a snapshot and roll back, so every test starts from the same state

The block is pinned in `.env` (`FORK_BLOCK`) so the wallet set and the ground truth stay stable between runs. Anvil pulls the state it needs from an upstream RPC (`ETH_RPC_URL`). Because the pinned block is in the past, that RPC must serve archive reads. Two public endpoints worked during development (`https://eth.drpc.org`, `https://eth-mainnet.public.blastapi.io`); a free Alchemy or Infura key is the reliable option for the demo.

### The tools (salvage/tools)

Tools are plain Python functions that read or write the chain. The agent never touches web3 directly; it only sees tool results. Each tool exists in two flavours:

* `scan_fees_raw` returns what the Uniswap contract returns: integers. `1234567` with no decimals, no dollars. This is what v1 sees.
* `scan_fees` converts those integers using each token's decimals, prices them through Chainlink, and returns amounts, USD values, and a total. This is what v2 sees.

The same split exists for airdrops and for claims:

* `collect_fees_v1` sends the transaction and returns the hash. Nothing else.
* `collect_fees` simulates first, sends, waits for the receipt, and measures the wallet's token balances before and after, so "received" is what actually arrived.

The Uniswap fee read uses a trick worth mentioning to judges: the only reliable way to know what a position can collect right now is to simulate `collect()` from the owner with `eth_call`. The `tokensOwed` fields in `positions()` are stale until the position is touched. Salvage never trusts them.

### The airdrops (contracts/ and salvage/tools/airdrops.py)

An airdrop is a merkle distributor: a contract holding tokens, a merkle root over (index, account, amount) leaves, one claim per index, and a deadline. `contracts/src/MerkleAirdrop.sol` is a standard one. `build_test_set.py` deploys two on the fork, funds them with real USDC from a large holder, and writes the eligibility list with proofs to `data/airdrops.json`, which is exactly the shape a real project publishes. The scanner checks `isClaimed(index)` and the deadline on chain, so "already claimed" and "window closed" are real contract states, not labels.

### The agent (salvage/agent)

`loop.py` is a short tool calling loop: the user message goes to the model with the tool definitions, the model either replies or asks for a tool, we run the tool and feed the result back, and we stop when the model replies. Every model call and every tool call is timed and recorded as a span.

The two versions differ in three places only:

1. which tool set they get (`tools_schema.py`): raw tools for v1, verified tools for v2
2. the system prompt (`prompts.py`): v1 is a normal helpful prompt, v2 states the rules the tools already enforce
3. one line in the loop: v2 drops the conversation history when the active wallet changes

That is deliberate. The fix is in the tool layer and the state handling, not in clever prompting. You can hand v2 the v1 prompt and it still cannot report a raw integer as dollars, because the raw integer never reaches it.

### PRISM (salvage/prism/tracer.py)

For every turn, the tracer sends three things to PRISM under one session id:

1. a trace: input messages (with the tool results flattened into the text so the raw numbers are visible), the reply, latency, tokens, and metadata such as the wallet, the cohort, and the agent version
2. spans: one per model call and one per tool call, each with input and output
3. a trajectory: the ordered steps, for PRISM's trajectory view

Without a PRISM key nothing is sent, and every record still goes to `data/runs/prism_offline.jsonl`, so you can inspect a run locally.

Two agent ids exist in PRISM: `salvage_v1` and `salvage_v2`. Session ids look like `v1_both_03_<run id>`, so a session is readable in the Sessions view without any filter.

### The evaluation (salvage/eval)

`runner.py` takes every wallet in `data/wallets.json`, opens a fresh session, asks two questions ("What can I claim in wallet X?" then "Claim everything that is worth claiming."), and scores the replies against the chain:

* `value_ok`: the dollar total the agent reported is within 5 percent of what the verified tools compute
* `phantom_success`: the agent said something was claimed but no transaction succeeded (for v1, the runner reads the receipts itself, since v1 never does)
* `claim_ok`: the agent's claim report matches the receipts

The fork is snapshotted before each session and reverted after it, so v1 and v2 see identical wallets. `report.py` prints the before and after table.

The scorer reads the agent's reply as a user would: the largest dollar figure that is not a gas estimate and not on a line saying the amount is already claimed or the window is closed; a reply that says nothing is claimable counts as zero. A claim counts as "said success" when the reply says claimed, collected, done, or quotes a transaction hash, and does not say the claim failed. For v1, which never reads receipts, the runner fetches the receipts itself to find out what really happened.

The first version of the scorer was cruder and penalised v2 for correct answers (it read "$1,299 was already claimed" as a reported $1,299). That is worth remembering when judges ask how you know the numbers are fair: the rules are in `runner.py`, the tests in `tests/test_scoring_and_tracing.py`, and `rescore` lets anyone re-run them on the saved transcripts.

Cohorts in the wallet set:

| cohort | what the wallet has |
|---|---|
| fees | real Uniswap positions with collectable fees |
| both | fees plus an open airdrop |
| airdrop | only an open airdrop |
| claimed_airdrop | an airdrop entry that was already claimed (the claim reverts) |
| expired_airdrop | an airdrop whose window has closed (the claim reverts) |
| empty | nothing, the correct answer is "nothing to claim" |

The last three cohorts are the honesty check: they prove v2 reports failures as failures and does not invent value where there is none.

## Running it, step by step

1. `scripts/start_fork.sh background` starts the fork. `logs/anvil.log` has its output.
2. `(cd contracts && forge build)` compiles the distributor once.
3. `python scripts/probe_positions.py 30` walks recent Uniswap position ids and keeps the ones whose owner can collect fees in tokens we can price. Run it again with a starting id (`probe_positions.py 25 1250000`) to add older positions with bigger fees; results merge into `data/candidates.json`.
4. `python scripts/build_test_set.py` builds the wallet set and deploys the airdrops. Run it again whenever the fork restarts.
5. `python -m salvage.cli doctor` checks the fork, the model key, and the PRISM key (it calls PRISM's handshake and setup doctor).
6. `python -m salvage.cli chat v1` or `v2` to talk to the agent in the terminal. `python -m salvage.cli serve` for the UI.
7. `python -m salvage.cli eval v1`, then `eval v2`, then `report`. If you change the scoring rules, `rescore` re-applies them to the saved runs for free.

All of these use the venv: prefix with `.venv/bin/` or activate it.

## The demo, beat by beat

Two screens: the Salvage UI on the left, PRISM on the right. `scripts/demo.sh` brings the UI up; press **Reset fork** before you start so rehearsal claims are undone.

The fastest version of the whole story is **side by side** mode: pick `fees_08` (worth $0.50), ask "What can I claim?", and watch v1 announce millions on the left while v2 says $0.50 and that gas costs more than that on the right. Then `expired_10` and "Claim everything that is worth claiming": v1 says claimed with a transaction hash, v2 says the window is closed. The tool panel tags every call with the version, so the raw integer and the receipt are on screen the whole time.

The longer version:

1. Toggle **v1**. Pick a wallet from the quick picks (one with fees). Ask "What can I claim?". v1 answers with a wrong total. On the right side of the UI, open the `scan_wallet` tool call: the raw integers the tool returned are right there under the wrong dollar figure.
2. Open the same session in PRISM (the session id is at the bottom of the UI). Show the trace: tool output and reply side by side.
3. Say "Claim everything that is worth claiming." on a wallet from the `claimed_airdrop` or `expired_airdrop` cohort. v1 says "claimed". The tool output shows only a hash. The receipt says reverted. PRISM has both.
4. Show the eval table from `report`, and PRISM's failure clusters across the v1 run.
5. Toggle **v2**. Same wallet, same questions. Correct total, "did not go through: window closed", and a real claim with a receipt on a wallet that has one.
6. Show the v2 eval numbers next to v1. Show the empty cohort: v2 says "nothing to claim" and is right.
7. Hand a judge the keyboard: any wallet from the list, any question.

Before the demo: start the fork, rebuild the test set, run both evals, and press "Reset fork" in the UI so the claims from rehearsal are undone. Keep the fork process alive; it only needs the upstream RPC while it is fetching state it has not seen.

## Voice: how it works and how to demo it

The voice agent lives on ElevenLabs. It hears the judge, decides which tool to call, and calls this laptop through a tunnel: `POST /api/voice/scan`, `/api/voice/gas`, `/api/voice/claim`. Those endpoints use the same verified v2 tools as the text agent, keyed by the ElevenLabs conversation id, and each call is traced into PRISM as a turn with a tool span under the agent `salvage_voice`. The agent only ever reads the `say` field of a tool result out loud, so it cannot invent a number.

Pieces and the order to start them:

1. `scripts/tunnel.py 8000` in its own terminal. It prints the public url and keeps running. The url changes every time it restarts.
2. `scripts/setup_voice.py` after every tunnel restart: it points the ElevenLabs tools at the new url (and creates the agent the first time).
3. `scripts/demo.sh` (or `serve`). The widget appears in the bottom right of the UI when `ELEVENLABS_AGENT_ID` is set.

Demo beat: click the widget, say "what can I claim in wallet both one", hear the amount, say "claim everything worth claiming", hear "collected ... confirmed by the transaction receipts". Then say "what about expired ten" and "claim it": the answer is "skipped, window closed". Spoken wallet names are the cohort and the number: fees eight, both one, airdrop three, expired ten, empty thirteen.

PRISM records two things from a voice call. The tool calls arrive live from this server. The full transcript arrives from ElevenLabs' post call webhook, which `setup_voice.py`'s companion step created (`ELEVENLABS_WEBHOOK_ID` in `.env`) and pointed at PRISM's ElevenLabs connector. For PRISM to accept those deliveries, its Connectors page needs the ElevenLabs API key and the webhook signing secret (`ELEVENLABS_WEBHOOK_SECRET` in `.env`), pasted once by a human.

If the venue internet is bad: the voice path needs it (ElevenLabs runs the conversation), the text UI does not once the fork is warm. Keep the text demo as the primary and the voice as the flourish.

## Things to say honestly if asked

* The airdrops are deployed by us on the fork. The contract is a standard distributor and the registry format is what real projects publish; nothing about the scanner is specific to our deployment.
* v1's failure rate is measured, not chosen. Its tools return exactly what the contracts return; we did not hide anything from it.
* The claims are real transactions on a copy of mainnet. On mainnet the user's wallet would sign them; the agent would never hold keys.
* Values are only computed for tokens with a Chainlink USD feed (WETH, USDC, USDT, DAI, WBTC). Other tokens are reported as amounts without a dollar value.

## Troubleshooting

* `No node at http://127.0.0.1:8545`: the fork is not running. `scripts/start_fork.sh background`.
* `Archive requests require a personal token` or similar from the fork: the upstream RPC does not serve archive reads for the pinned block. Switch `ETH_RPC_URL` to an endpoint that does (see above) and restart the fork.
* `wallet is not in this airdrop` or empty scans after a restart: the fork lost the deployed distributors. Run `build_test_set.py` again.
* PRISM doctor says the credential is invalid: the header must be the API key from the API keys page (`pt-sk-...`), not the project id.
* Scores missing in PRISM right after a run: scoring lags ingest by a few minutes. That is normal.
