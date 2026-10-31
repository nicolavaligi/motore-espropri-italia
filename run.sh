#!/usr/bin/env bash
# Launcher locale Motore Espropri Italia
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "⚙️ Configurazione ambiente uv..."
    uv venv .venv
    source .venv/bin/activate
    uv pip install fastapi uvicorn
else
    source .venv/bin/activate
fi

echo "🚀 Avvio Motore Espropri Italia su http://127.0.0.1:8000"
exec uvicorn server:app --host 127.0.0.1 --port 8000 --reload
