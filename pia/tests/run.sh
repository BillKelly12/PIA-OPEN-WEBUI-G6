#!/usr/bin/env bash
# Run the Group 6 privacy tests on the official Open WebUI test harness.
#
# What it does: fetches the official regression suite (github.com/open-webui/tests, BSD-3) at the
# commit of 14 Oct 2026 (the day of our Open WebUI v0.12.2), copies our tests into its
# integration/ folder, and runs them against OUR checkout. Nothing in Open WebUI is modified.
#
# Usage (from the repo root):   bash pia/tests/run.sh [pytest arguments]
# Optional variables:
#   SUITE_DIR   where to keep the suite (default: ../owui-tests, next to the repo)
#   PY          python with the dependencies; if unset, a venv is created in $SUITE_DIR/venv
#   BACKEND     our backend folder (default: <repo>/backend)
set -euo pipefail
SUITE_COMMIT="c7231872b6f46357a38b2378895aefed0039f491"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SUITE_DIR="${SUITE_DIR:-$REPO/../owui-tests}"
BACKEND="${BACKEND:-$REPO/backend}"
[ -f "$BACKEND/requirements.txt" ] || { echo "No backend/requirements.txt in $BACKEND: run this from a full clone of the fork."; exit 1; }

if [ ! -d "$SUITE_DIR/suite/.git" ]; then
  mkdir -p "$SUITE_DIR"
  git clone --quiet https://github.com/open-webui/tests.git "$SUITE_DIR/suite"
fi
git -C "$SUITE_DIR/suite" -c advice.detachedHead=false checkout --quiet "$SUITE_COMMIT"

if [ -z "${PY:-}" ]; then
  if [ ! -x "$SUITE_DIR/venv/bin/python" ]; then
    echo "Creating the Python environment (once, about 1-2 minutes)..."
    grep -vE '^(accelerate|colbert-ai|elasticsearch|faster-whisper|opencv-python-headless|opensearch-py|oracledb|pinecone|playwright|pymilvus|qdrant-client|rapidocr|sentence-transformers|sentencepiece|transformers|unstructured|weaviate-client)' \
      "$BACKEND/requirements.txt" > "$SUITE_DIR/req-light.txt"
    uv venv --python 3.12 "$SUITE_DIR/venv"
    uv pip install --python "$SUITE_DIR/venv/bin/python" -r "$SUITE_DIR/req-light.txt" -r "$SUITE_DIR/suite/pyproject.toml"
  fi
  PY="$SUITE_DIR/venv/bin/python"
fi

rm -rf "$SUITE_DIR/suite/integration/privacy"
cp -r "$HERE/privacy" "$SUITE_DIR/suite/integration/privacy"
cd "$SUITE_DIR/suite"
export OPEN_WEBUI_SOURCE_DIR="$BACKEND" OWUI_TEST_PRELOAD=0
exec "$PY" -m pytest integration/privacy -p no:cacheprovider "$@"
