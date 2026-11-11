#!/usr/bin/env bash
# Runs the ten privacy tests INSIDE the official Open WebUI v0.12.2 Docker image
# (its Python 3.11 and its SQLite), against the backend of the branch you are on.
#
# Usage, from the root of your clone, on the branch you want to test:
#     bash pia/tests/run_tests_in_docker.sh           # all ten tests
#     bash pia/tests/run_tests_in_docker.sh -v -k d3  # extra pytest arguments
#
# Nothing is installed on your computer: the Python packages go into a throw-away container.
# The first run downloads packages (a few minutes); the image itself is already on your machine.
set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/open-webui/open-webui:v0.12.2}"
SUITE_COMMIT="c7231872b6f46357a38b2378895aefed0039f491"   # official suite, 14 Oct 2026 (same as run.sh)

command -v docker >/dev/null || { echo "ERROR: docker is not installed."; exit 1; }
docker info >/dev/null 2>&1 || {
  echo "ERROR: cannot talk to Docker. Is it running? If you see 'permission denied', run:"
  echo "       sudo usermod -aG docker \$USER   (then log out and in again)"; exit 1; }

REPO="$(git rev-parse --show-toplevel)"
[ -d "$REPO/backend/open_webui" ] && [ -d "$REPO/pia/tests/privacy" ] || { echo "ERROR: run this inside the clone of the fork."; exit 1; }
SUITE_ROOT="${SUITE_DIR:-$REPO/../owui-tests}"

mkdir -p "$SUITE_ROOT"
[ -d "$SUITE_ROOT/suite/.git" ] || git clone --quiet https://github.com/open-webui/tests.git "$SUITE_ROOT/suite"
git -C "$SUITE_ROOT/suite" -c advice.detachedHead=false checkout --quiet "$SUITE_COMMIT"
rm -rf "$SUITE_ROOT/suite/integration/privacy"
cp -r "$REPO/pia/tests/privacy" "$SUITE_ROOT/suite/integration/privacy"

echo "Branch : $(git -C "$REPO" branch --show-current)  ($(git -C "$REPO" rev-parse --short HEAD))"
echo "Image  : $IMAGE"
echo

docker run --rm --user root --entrypoint bash \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -e OPEN_WEBUI_SOURCE_DIR=/work/backend \
  -e OWUI_TEST_PRELOAD=0 \
  -v "$REPO":/work \
  -v "$SUITE_ROOT/suite":/suite \
  -w /suite \
  "$IMAGE" -c '
set -e
python --version
python - <<PY
import sqlite3
con = sqlite3.connect(":memory:")
print("SQLite", sqlite3.sqlite_version, "| secure_delete =", con.execute("pragma secure_delete").fetchone()[0])
PY
echo "Installing the test suite packages (first run only takes a few minutes)..."
python - <<PY
import subprocess, sys, tomllib
deps = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--no-input", "--disable-pip-version-check", *deps])
PY
echo "Running the tests..."
exec python -m pytest integration/privacy -p no:cacheprovider "$@"
' _ "$@"
