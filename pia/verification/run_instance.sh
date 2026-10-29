#!/usr/bin/env bash
# Start a throw-away Open WebUI backend wired to the stub Ollama and the egress logger.
# Usage: run_instance.sh <workdir> <repo_root> <venv_python>
# Nothing here touches application code. Data lands in <workdir>/data.
set -euo pipefail
# The fake Ollama listens on STUB_PORT (default 11435) so it never clashes with a real Ollama on 11434.
STUB_PORT="${STUB_PORT:-11435}"
WORK="$1"; REPO="$2"; PY="$3"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$WORK/data" "$WORK/logs"

"$PY" "$HERE/stub_ollama.py" "$STUB_PORT" "$WORK/logs/ollama_requests.jsonl" >"$WORK/logs/stub.out" 2>&1 &
echo $! >"$WORK/stub.pid"
"$PY" "$HERE/egress_proxy.py" 3128 "$WORK/logs/egress.jsonl" >"$WORK/logs/proxy.out" 2>&1 &
echo $! >"$WORK/proxy.pid"
sleep 1

cd "$REPO/backend"
export PYTHONPATH="$REPO/backend"
export DATA_DIR="$WORK/data"
export WEBUI_SECRET_KEY="verification-only-secret"
export OLLAMA_BASE_URL="http://127.0.0.1:${STUB_PORT}"
export RAG_EMBEDDING_ENGINE="ollama"
export RAG_OLLAMA_BASE_URL="http://127.0.0.1:${STUB_PORT}"
export RAG_EMBEDDING_MODEL="stub-embed"
export HTTP_PROXY="http://127.0.0.1:3128" HTTPS_PROXY="http://127.0.0.1:3128"
export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY"
export NO_PROXY="127.0.0.1,localhost" no_proxy="127.0.0.1,localhost"
export HF_HUB_OFFLINE=1   # avoid hanging on blocked model downloads in the sandbox
"$PY" -m uvicorn open_webui.main:app --host 127.0.0.1 --port 8080 >"$WORK/logs/webui.out" 2>&1 &
echo $! >"$WORK/webui.pid"
echo "started: webui pid $(cat "$WORK/webui.pid")"
