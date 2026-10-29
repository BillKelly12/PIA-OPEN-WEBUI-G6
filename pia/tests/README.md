# Privacy tests (Group 6)

Eight tests, one per finding, written for pytest on the **official Open WebUI test harness**
(repository `open-webui/tests`, BSD-3). They test Open WebUI **v0.12.2** (commit `6a18585`) from the
outside: the HTTP API, the data folder, and the requests sent to a model provider. No test depends on
what a model answers (course rule 5). All personal data in them is synthetic.

**Today all eight FAIL on the unmodified code, on purpose.** Reproduced on two machines on 29 Oct 2026 (Linux, Python 3.12.3 and 3.12.15): the same 8 failures with the same messages. A test turns green only when the
mitigation for its finding is implemented in the fork.

## Run
From the root of a full clone of the fork (it must contain `backend/`), with `git` and `uv` installed:
```
bash pia/tests/run.sh            # about 1-2 minutes the first time, 15 seconds afterwards
bash pia/tests/run.sh -v         # test names; add -k b3 to run one finding
```
The script clones the official suite next to the repo (`../owui-tests`) at the commit of 14 Oct 2026
(the day of our Open WebUI version), builds a Python environment, copies `pia/tests/privacy/` into the
suite's `integration/` folder and runs it against `backend/`. It does not touch Open WebUI.
`last_run_output.txt` is the output of the current run (use it, or a fresh run, for the screenshot).

## Tests and findings
| Test | Finding | What the test does | Fails today because | GDPR |
|---|---|---|---|---|
| `test_d1_...` | Deleting a file | Upload, delete through the API, read the vector store | 1 chunk with the interview text is still stored | 17, 5(1)(e) |
| `test_d2_..._file_chunks` | Deleting a user | Admin deletes the user, read the vector store | the user's file chunks are still stored | 17, 5(1)(e) |
| `test_d2_..._memory_vectors` | Deleting a user | same | the user's memory vectors are still stored | 17, 5(1)(e) |
| `test_d2_..._uploaded_files` | Deleting a user | same, plus the file API and the uploads folder | the file still answers HTTP 200 and its copy is on disk | 17, 5(1)(e) |
| `test_b1_...` | B1 external model gets the passages | Ask about an attached document, read what the provider received | name, e-mail and phone are in the request | 5(1)(b)(c), 25, 28 |
| `test_b2_b4_...` | B2+B4 external embeddings, no per-document rule | Upload, read what the embedding provider received | the same identifiers are in the upload request | 5(1)(c), 25, Ch. V |
| `test_b3_...` | B3 background tasks | Chat with title/tags/follow-ups on, read the extra requests | 3 task requests carry the name and e-mail | 5(1)(c), 25 |
| `test_b7_...` | B7 shared chat | Share a chat that used a private knowledge base with a colleague | the colleague, who cannot open the knowledge base, reads the e-mail | 5(1)(f), 25 |

The provider-side tests pass when no identifier reaches the provider. A pseudonymisation gateway or a
rule that keeps the call local both satisfy them; which mitigation we implement is a team decision.

## Method (how to cite it)
The tests follow the official suite's own contract (`docs/regression-test-contract.md` in `open-webui/tests`): a regression test is pinned to one problem, must fail before the fix and pass after it, and states in its docstring what it covers. The harness (fake provider, instance start-up, accounts) is the Open WebUI project's work, BSD-3 licence; our tests are in `privacy/`.

## Notes for reviewers (what each test does *not* prove)
- The harness provider is a scripted stand-in. The tests show **what Open WebUI sends**, not what a real provider does with it (that stays an assumption, handled by contract).
- The harness uses OpenAI-type embeddings by default. B2/B4 therefore tests the configuration the lab would have if it chose external embeddings, not the default of Open WebUI (local embeddings).
- B7 covers retrieval from a knowledge base. A file stored on the chat message is readable through a share by design (`utils/access_control/files.py`), so it is not a leak.
- The suite's own boilerplate "SKEPTIC VERIFICATION" note appears after failures. We did that check: each failure was read, and every precondition (the data exists before the deletion, the document was retrieved, the colleague has no access) is asserted inside the test.
- Version: the official suite follows Open WebUI's development branch. We pin it to the commit of 14 Oct so that it matches v0.12.2.