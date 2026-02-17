#!/bin/bash
# Solar Intelligence — Data Update Wrapper
# Usage: ./update-local.sh           (fetch only)
#        ./update-local.sh --push    (fetch + commit + push)
set -e
cd "$(dirname "$0")"
PYTHON="${PYTHON:-$(command -v python3 || echo .venv/bin/python3)}"
exec "$PYTHON" update_data.py "$@"
