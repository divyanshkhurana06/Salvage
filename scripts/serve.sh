#!/usr/bin/env bash
# Start the Salvage web UI on the given port (default 8000).
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m salvage.cli serve "${1:-8000}"
