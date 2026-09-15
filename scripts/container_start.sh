#!/usr/bin/env bash
# Boot sequence for the container (and for any fresh machine): forks, wallet set, health check, UI.
# Every setting comes from the environment (the platform's variables, or --env-file .env locally).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.foundry/bin:$PATH"
mkdir -p logs data/runs

PY="${PYTHON:-python}"
[ -x .venv/bin/python ] && PY=.venv/bin/python

echo "--- forks ---"
scripts/start_fork.sh background
if [ -n "${BASE_RPC_URL:-}" ]; then
  scripts/start_fork.sh background base || echo "base fork did not start, continuing on Ethereum only"
fi

echo "--- wallet set ---"
if [ ! -f data/candidates.json ]; then
  echo "probing Ethereum for real positions with fees (a few minutes)"
  "$PY" scripts/probe_positions.py 30
fi
if [ -n "${BASE_RPC_URL:-}" ] && [ ! -f data/candidates_base.json ]; then
  echo "probing Base for real positions with fees"
  "$PY" scripts/probe_positions.py 8 --chain base || true
fi
"$PY" scripts/build_test_set.py

echo "--- doctor ---"
"$PY" -m salvage.cli doctor || true

echo "--- serving on ${SERVE_HOST:-0.0.0.0}:${PORT:-8000} ---"
exec "$PY" -m salvage.cli serve "${PORT:-8000}"
