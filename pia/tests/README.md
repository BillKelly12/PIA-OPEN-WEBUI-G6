# Privacy tests (Group 6)

Ten tests, one per finding, written for pytest on the **official Open WebUI test harness**
(repository `open-webui/tests`, BSD-3). They test Open WebUI **v0.12.2** (commit `6a18585`) from the
outside: the HTTP API, the data folder, and the requests sent to a model provider. No test depends on
what a model answers (course rule 5). All personal data in them is synthetic.

**All ten FAIL on the unmodified code, on purpose.** The first eight were reproduced on two machines on 29 Oct 2026 (Linux, Python 3.12.3 and 3.12.15): the same 8 failures with the same messages. D3 and D4 were added on 10 Nov 2026 (`run_before_fix.txt`: 10 failed). A test turns green only when the
mitigation for its finding is implemented in the fork.

**On branch `pia/fix-deletion` the six deletion tests (D1 to D4) PASS** (`run_after_fix.txt`: 6 passed, 4 failed).
The four provider and sharing tests (B1, B2/B4, B3, B7) still fail; their mitigations are not implemented yet.
See "Implemented fixes" below.

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
| `test_d3_...` | Deleting a chat (report issue I4) | Store a chat, delete it through the API, read `webui.db` and `webui.db-wal` as raw bytes | the deleted text is still readable in `webui.db-wal` | 17, 5(1)(e), 5(1)(f) |
| `test_d4_...` | Deleting a rated chat (issue I4) | Rate an answer with the browser's payload (full chat copy), delete the chat, read the admin's feedback export | the export still returns the deleted chat | 17, 5(1)(e) |
| `test_b1_...` | B1 external model gets the passages | Ask about an attached document, read what the provider received | name, e-mail and phone are in the request | 5(1)(b)(c), 25, 28 |
| `test_b2_b4_...` | B2+B4 external embeddings, no per-document rule | Upload, read what the embedding provider received | the same identifiers are in the upload request | 5(1)(c), 25, Ch. V |
| `test_b3_...` | B3 background tasks | Chat with title/tags/follow-ups on, read the extra requests | 3 task requests carry the name and e-mail | 5(1)(c), 25 |
| `test_b7_...` | B7 shared chat | Share a chat that used a private knowledge base with a colleague | the colleague, who cannot open the knowledge base, reads the e-mail | 5(1)(f), 25 |

The provider-side tests pass when no identifier reaches the provider. A pseudonymisation gateway or a
rule that keeps the call local both satisfy them; which mitigation we implement is a team decision.

## Implemented fixes (branch `pia/fix-deletion`, findings D1 to D4)
| Finding | Cause in v0.12.2 | Fix | Files |
|---|---|---|---|
| D1 file chunks stay | `delete(collection_name=...)` without ids or a filter deletes nothing in Chroma | drop the whole `file-{id}` collection | `routers/files.py`, `utils/erasure.py` |
| D2 user data stays | `Users.delete_user_by_id` removes only groups, chats and the account | before the account goes, remove the user's files (row, stored copy, chunks, knowledge-base links), memories and their vectors, notes, folders and ratings | `routers/users.py`, `utils/erasure.py` |
| D3 text in database files | deleted rows stay in the write-ahead file and in free pages | `PRAGMA secure_delete=ON` on every connection, plus a `wal_checkpoint(TRUNCATE)` after each deletion (SQLite only) | `env.py`, `internal/db.py`, `utils/erasure.py` |
| D4 rating keeps a chat copy | the browser stores the full chat with each rating; chat deletion ignores it | on chat deletion, remove the copy and the chat link but keep the rating, so the model leaderboard still works | `routers/chats.py`, `utils/erasure.py` |

Why D3 needs both parts (stand-alone SQLite check, WAL mode): with only `secure_delete` the old page is still in the main file until the next checkpoint; with only the checkpoint the text stays in the main file's free space; with both, it is found nowhere.

Regression check: 149 of Open WebUI's own integration tests that touch these routes (user administration, SCIM deprovisioning, file deletion, document ingestion, chat sharing, chat store, tags, leaderboard, memories, notes, observability) were run on the fixed code: 145 passed. The 4 failures also fail on the unmodified code (a package left out of the light install, and a blocked download of a tokenizer file), so they are not caused by the fixes.

Known limits: knowledge bases owned by a deleted user are not removed, because other users may have been granted access to them. Backups and copies of the data folder made before a deletion are outside the application; they need a backup retention policy (Part 3). The fix covers the default SQLite database; on PostgreSQL deleted rows are cleaned by `VACUUM`, which we did not test.

## Method (how to cite it)
The tests follow the official suite's own contract (`docs/regression-test-contract.md` in `open-webui/tests`): a regression test is pinned to one problem, must fail before the fix and pass after it, and states in its docstring what it covers. The harness (fake provider, instance start-up, accounts) is the Open WebUI project's work, BSD-3 licence; our tests are in `privacy/`.

## Notes for reviewers (what each test does *not* prove)
- The harness provider is a scripted stand-in. The tests show **what Open WebUI sends**, not what a real provider does with it (that stays an assumption, handled by contract).
- The harness uses OpenAI-type embeddings by default. B2/B4 therefore tests the configuration the lab would have if it chose external embeddings, not the default of Open WebUI (local embeddings).
- B7 covers retrieval from a knowledge base. A file stored on the chat message is readable through a share by design (`utils/access_control/files.py`), so it is not a leak.
- The suite's own boilerplate "SKEPTIC VERIFICATION" note appears after failures. We did that check: each failure was read, and every precondition (the data exists before the deletion, the document was retrieved, the colleague has no access) is asserted inside the test.
- Version: the official suite follows Open WebUI's development branch. We pin it to the commit of 14 Oct so that it matches v0.12.2.