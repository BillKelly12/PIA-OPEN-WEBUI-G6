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

## Run (Linux, Python 3.12 environment with the backend requirements installed)
```
STUB_REPLY_CHARS=1500 bash pia/verification/run_instance.sh /tmp/work $(pwd) /path/to/venv/bin/python
# wait until http://127.0.0.1:8080/health answers
cd pia/verification && python run_scenario.py /tmp/work
```
Use a fresh work folder each time (the script creates the first account). Stop the three processes afterwards (pids are in `/tmp/work/*.pid`).

## Caveats (also stated in the analysis)
Started from source, not the Docker image; API only (no browser); stub model; `HF_HUB_OFFLINE=1`; synthetic markers instead of personal data; SQLite and Chroma defaults. The mermaid export needs Chromium: `mmdc -i x.mmd -o x.svg -p puppeteer.json` with `{"executablePath": "<chrome path>", "args": ["--no-sandbox"]}`.
