#!/usr/bin/env bash
set -euo pipefail
MOTORE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MOTORE_DIR"
echo "Motore Espropri Italia: http://127.0.0.1:${PORT:-8000}"
exec uv run --frozen --no-dev uvicorn server:app --host 127.0.0.1 --port "${PORT:-8000}"
