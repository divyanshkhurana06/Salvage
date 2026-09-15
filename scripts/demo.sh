#!/usr/bin/env bash
# One command to bring the whole demo up: fork, contracts, wallet set, health check, web UI.
#   scripts/demo.sh            start what is missing and serve on port 8000
#   scripts/demo.sh rebuild    force a fresh wallet set (after a fork restart)
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.foundry/bin:$PATH"

if [ ! -f .env ]; then
  echo "no .env file. Copy .env.example to .env and fill in the keys first." >&2
  exit 1
fi
set -a; . ./.env; set +a
PORT="${FORK_PORT:-8545}"

started_fork=0
if curl -s -X POST -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' "http://127.0.0.1:$PORT" | grep -q result; then
  echo "fork already running on port $PORT"
else
  scripts/start_fork.sh background
  started_fork=1
fi

# the second chain, when an upstream for it is configured
if [ -n "${BASE_RPC_URL:-}" ]; then
  BASE_PORT="${BASE_FORK_PORT:-8546}"
  if curl -s -X POST -H 'Content-Type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' "http://127.0.0.1:$BASE_PORT" | grep -q result; then
    echo "base fork already running on port $BASE_PORT"
  else
    scripts/start_fork.sh background base || echo "base fork did not start, continuing on Ethereum only"
  fi
  if [ ! -f data/candidates_base.json ]; then
    echo "probing Base for real positions with fees (a minute or two)"
    .venv/bin/python scripts/probe_positions.py 12 --chain base || true
  fi
fi

if [ ! -f contracts/out/MerkleAirdrop.sol/MerkleAirdrop.json ]; then
  echo "compiling the airdrop contract"
  (cd contracts && forge build)
fi

if [ ! -f data/candidates.json ]; then
  echo "probing for real positions with fees (a few minutes)"
  .venv/bin/python scripts/probe_positions.py 30
fi

# the airdrop contracts live only in the running fork, so rebuild when the fork is fresh
needs_build=0
if [ "${1:-}" = "rebuild" ] || [ "$started_fork" = "1" ] || [ ! -f data/wallets.json ]; then
  needs_build=1
else
  needs_build=$(.venv/bin/python - <<'EOF'
import json
from salvage.chain import get_chain
from salvage.tools.airdrops import load_registry
reg = load_registry()
chain = get_chain()
ok = bool(reg) and all(len(chain.w3.eth.get_code(chain.checksum(d["address"]))) > 2 for d in reg)
print(0 if ok else 1)
EOF
)
fi
if [ "$needs_build" = "1" ]; then
  echo "building the wallet set on the fork"
  .venv/bin/python scripts/build_test_set.py
fi

# voice: open the tunnel and point the ElevenLabs agent at it, when the keys are present
if [ -n "${ELEVENLABS_API_KEY:-}" ] && [ -n "${NGROK_AUTHTOKEN:-}" ]; then
  if pgrep -f "scripts/tunnel.py" >/dev/null; then
    echo "tunnel already running: $(cat data/public_url.txt 2>/dev/null)"
  else
    rm -f data/public_url.txt
    nohup .venv/bin/python scripts/tunnel.py "${SERVE_PORT:-8000}" > logs/tunnel.log 2>&1 &
    for i in $(seq 1 40); do sleep 1; [ -f data/public_url.txt ] && break; done
    echo "tunnel: $(cat data/public_url.txt 2>/dev/null || echo 'did not start, see logs/tunnel.log')"
  fi
  .venv/bin/python scripts/setup_voice.py | tail -3 || echo "voice setup failed, the text demo still works"
fi

echo "--- doctor ---"
.venv/bin/python -m salvage.cli doctor || true
echo "--- serving on http://127.0.0.1:8000 ---"
exec scripts/serve.sh 8000
