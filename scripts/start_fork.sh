#!/usr/bin/env bash
# Start a local Anvil fork of Ethereum mainnet using the settings in .env.
# Usage: scripts/start_fork.sh            (foreground)
#        scripts/start_fork.sh background (detached, logs to logs/anvil.log)
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

ETH_RPC_URL="${ETH_RPC_URL:-https://ethereum-rpc.publicnode.com}"
PORT="${FORK_PORT:-8545}"
ARGS=(--fork-url "$ETH_RPC_URL" --port "$PORT" --chain-id 1)
if [ -n "${FORK_BLOCK:-}" ]; then
  ARGS+=(--fork-block-number "$FORK_BLOCK")
fi

mkdir -p logs
echo "starting anvil fork of $ETH_RPC_URL on port $PORT (block: ${FORK_BLOCK:-latest})"
if [ "${1:-}" = "background" ]; then
  nohup anvil "${ARGS[@]}" --silent > logs/anvil.log 2>&1 &
  echo $! > logs/anvil.pid
  for i in $(seq 1 60); do
    sleep 1
    if curl -s -X POST -H 'Content-Type: application/json' \
      --data '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' "http://127.0.0.1:$PORT" | grep -q result; then
      echo "fork is up (pid $(cat logs/anvil.pid))"
      exit 0
    fi
  done
  echo "fork did not come up, see logs/anvil.log" >&2
  exit 1
else
  exec anvil "${ARGS[@]}"
fi
