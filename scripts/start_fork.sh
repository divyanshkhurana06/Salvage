#!/usr/bin/env bash
# Start a local Anvil fork of Ethereum mainnet or Base using the settings in .env.
# Usage: scripts/start_fork.sh [background] [ethereum|base]
#        scripts/start_fork.sh                    Ethereum, foreground
#        scripts/start_fork.sh background         Ethereum, detached, logs to logs/anvil.log
#        scripts/start_fork.sh background base    Base, detached, logs to logs/anvil_base.log
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

MODE="${1:-foreground}"
CHAIN="${2:-ethereum}"
case "$CHAIN" in
  ethereum)
    UPSTREAM="${ETH_RPC_URL:-https://ethereum-rpc.publicnode.com}"; PORT="${FORK_PORT:-8545}"; CHAIN_ID=1; BLOCK="${FORK_BLOCK:-}"; LOG=logs/anvil.log; PIDFILE=logs/anvil.pid ;;
  base)
    UPSTREAM="${BASE_RPC_URL:-https://base-mainnet.public.blastapi.io}"; PORT="${BASE_FORK_PORT:-8546}"; CHAIN_ID=8453; BLOCK="${BASE_FORK_BLOCK:-}"; LOG=logs/anvil_base.log; PIDFILE=logs/anvil_base.pid ;;
  *)
    echo "unknown chain $CHAIN (ethereum or base)" >&2; exit 1 ;;
esac

ARGS=(--fork-url "$UPSTREAM" --port "$PORT" --chain-id "$CHAIN_ID" --retries 10 --fork-retry-backoff 1000 --timeout 60000)
if [ -n "$BLOCK" ]; then
  ARGS+=(--fork-block-number "$BLOCK")
fi
if [ "$CHAIN" = "base" ]; then
  # Base blocks carry a base fee around 0.006 gwei; anvil would otherwise quote 1 gwei, which would make gas on Base look like Ethereum
  ARGS+=(--gas-price "${BASE_GAS_PRICE_WEI:-6000000}" --base-fee "${BASE_GAS_PRICE_WEI:-6000000}" --compute-units-per-second 200)
fi

mkdir -p logs
echo "starting anvil fork of $CHAIN ($UPSTREAM) on port $PORT (block: ${BLOCK:-latest})"
if [ "$MODE" = "background" ]; then
  nohup anvil "${ARGS[@]}" --silent > "$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  for i in $(seq 1 90); do
    sleep 1
    if curl -s -X POST -H 'Content-Type: application/json' \
      --data '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' "http://127.0.0.1:$PORT" | grep -q result; then
      echo "$CHAIN fork is up (pid $(cat "$PIDFILE"))"
      exit 0
    fi
  done
  echo "$CHAIN fork did not come up, see $LOG" >&2
  exit 1
else
  exec anvil "${ARGS[@]}"
fi
