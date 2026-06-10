#!/bin/bash
# Run the REAL tradepilot stack locally (no docker): gateway + app + chat UI.
# Reads .env. Requires at least LITELLM_API_KEY (Groq) to be set there.
set -eu
cd "$(dirname "$0")/.."

if grep -q "PASTE_GROQ_KEY_HERE" .env; then
    echo "ERROR: paste your Groq API key into .env (LITELLM_API_KEY) first."
    echo "Get one free at https://console.groq.com"
    exit 1
fi

cleanup() { kill 0 2>/dev/null; }
trap cleanup EXIT

echo "starting gateway on :4706 ..."
uv run uvicorn gateway.main:app --host 127.0.0.1 --port 4706 &

echo "starting app on :4700 ..."
uv run uvicorn src.main:app --host 127.0.0.1 --port 4700 &

sleep 3
echo "starting chat UI on :4705 ..."
APP_BASE_URL=http://localhost:4700 uv run streamlit run tools/chat_ui.py \
    --server.address 127.0.0.1 --server.port 4705 --server.headless true
