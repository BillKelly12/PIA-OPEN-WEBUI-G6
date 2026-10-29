# Verification harness (describes behaviour; does not modify application code)

Purpose: every statement tagged "VERIFIED (run R##)" in `pia/data-flow-analysis.md` comes from these scripts.

| File | What it does |
|---|---|
| `stub_ollama.py` | Stand-in for Ollama. Answers the endpoints Open WebUI calls with fixed text and fixed 16-number vectors, and logs every request (JSONL). It is not a model. |
| `egress_proxy.py` | Local proxy that logs every outbound CONNECT/GET destination and refuses it (403). Evidence of what leaves the server. |
| `run_instance.sh` | Starts stub + proxy + backend from source with a throw-away data folder. |
| `run_scenario.py` | Replays the scenario (accounts, upload, RAG turn, share, admin reads, deletions, temporary chat) and prints one line per observation R01–R14. |
| `measure_volumes.py` | R15: storage growth per document and per chat turn. |
| `inspect_state.py`, `counts.py` | Look at the data folder: files, non-empty tables, vector collections, where a text marker survives. |
| `last_run_output.txt` | Output of the latest replay (all 14 lines "OBSERVED"). |
| `volumes_result.json` | Output of the volume measurement. |

## Run (Linux or macOS or WSL; needs Python 3.12 and `uv`)
Tested from a clean install on 29 Oct 2026 (all 14 lines OBSERVED). `<repo>` is your clone of the fork at commit `6a18585`. Paths below assume you run from `<repo>`.

**1. One-time setup: Python environment (about 1 minute).** Open WebUI needs Python 3.11 or 3.12 (not 3.13). We skip the heavy packages (model libraries, other vector databases) because the stub never uses them.
```
pip install uv                     # or: curl -LsSf https://astral.sh/uv/install.sh | sh
grep -vE '^(accelerate|colbert-ai|elasticsearch|faster-whisper|opencv-python-headless|opensearch-py|oracledb|pinecone|playwright|pymilvus|qdrant-client|rapidocr|sentence-transformers|sentencepiece|transformers|unstructured|weaviate-client)' backend/requirements.txt > /tmp/req-light.txt
uv venv --python 3.12 /tmp/venv
uv pip install --python /tmp/venv/bin/python -r /tmp/req-light.txt
```

**2. Start the test instance** (fresh work folder every time; the scenario creates the first account):
```
rm -rf /tmp/work && mkdir -p /tmp/work
STUB_REPLY_CHARS=1500 bash pia/verification/run_instance.sh /tmp/work $(pwd) /tmp/venv/bin/python
until curl -s -o /dev/null http://127.0.0.1:8080/health; do sleep 2; done   # about 10 seconds
```

**3. Replay the scenario and compare:**
```
cd pia/verification && /tmp/venv/bin/python run_scenario.py /tmp/work | tee /tmp/my_run.txt
```
Expected: 14 lines R01–R14 ending in `SUMMARY`, all `OBSERVED`. Compare with `last_run_output.txt` (random ids and paths differ; the codes and counts must match). A line marked `DIFFERS` means our claim does not hold on your machine: tell the team.

**4. Stop everything:** `for f in /tmp/work/*.pid; do kill $(cat $f); done`

Ports used: 8080 (Open WebUI), 11434 (stub Ollama), 3128 (egress logger). Free them first if another program uses them. Windows: use WSL.

**Optional:** `measure_volumes.py` produces R15 (storage growth); it needs the data folder and an ordinary user token, see its header comment.

## Caveats (also stated in the analysis)
Started from source, not the Docker image; API only (no browser); stub model; `HF_HUB_OFFLINE=1`; synthetic markers instead of personal data; SQLite and Chroma defaults. The mermaid export needs Chromium: `mmdc -i x.mmd -o x.svg -p puppeteer.json` with `{"executablePath": "<chrome path>", "args": ["--no-sandbox"]}`.
