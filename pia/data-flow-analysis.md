# Open WebUI — Data-Flow Analysis for the Research-Lab Use Case (Package 1)

> Description only. No threat analysis, no GDPR mapping, no fixes in this document (Packages 2 and 3).
> Companion file: `pia/architecture.md` (diagrams, IDs `E/P/DS/A/F/TB`). Code version: Open WebUI v0.12.2, commit `6a18585ff4c2e5f6805f682222cfbc46dc669ef8`.
> Tags: **VERIFIED (code)** = seen in source at `path:line`; **VERIFIED (doc)** = seen in the repository's deployment files; **VERIFIED (run R##)** = observed on a running instance (Appendix A, replayable with `pia/verification/run_scenario.py`); **HYPOTHESIS** = not seen, listed in section 8 with a local check.
> Limits of the runs: started from source (Docker Hub was not reachable), API only (browser frontend not run), stub Ollama (records requests, answers with fixed text), egress proxy (records and refuses outbound connections), synthetic data, SQLite + Chroma defaults.

## 1. Scenario and scope

**Scenario.** A university research lab runs one self-hosted Open WebUI instance. One person (supervisor or IT contact) administers it. A small group of PhD students and researchers use it. Inference is local (Ollama), so prompts and documents are not sent to a cloud model. Users upload unpublished papers, thesis drafts and sometimes interview or survey data and ask questions about them (document-based answers, "RAG"). Users can share a conversation by link.

**Steps followed (the same order as section 5):** sign in → chat → upload a draft → ask a question about it → share the chat → admin looks at the system → delete a chat, a file, a user → what leaves the server → logs and backups.

**Tested configuration (mentioned only as such).** Default settings of v0.12.2; SQLite database; Chroma vector store; local upload folder; embeddings requested from the (stub) Ollama through its `/api/embed` endpoint; chat requests to its `/api/chat` endpoint. The specific language model is not part of the analysis.

**In scope.** Data flows, storage, access control, retention, deletion, sharing, and the power gap between the admin and ordinary users.

**Out of scope (stated explicitly).**
- *Model training and memorisation.* The deployment does not train or fine-tune on user data, so whether a model could memorise or reproduce it is not analysed here. (That the deployment does not train is the use-case assumption; no training feature was examined.)
- *Model choice and answer quality.* Nothing here depends on what a model answers; all runtime checks are made on stored data, network requests and database/vector-store state.
- Features switched off by default and not part of the use case are mentioned only to say they are off: channels, web search, API keys, image generation (`backend/open_webui/config.py:2056, 1168, 1952, 1360`; VERIFIED (code)).

**Data subjects.** The people in the data, not only the account holders: students and supervisors who chat, co-authors named in drafts, and interviewees or survey respondents whose words sit in uploaded transcripts. Most of the latter never see the system.

## 2. Stakeholders and roles

The legal roles below are the **assumptions of this assessment** for the use case; the software has no notion of "controller" or "processor". (HYPOTHESIS for the legal characterisation; the technical facts in the last column are tagged.)

| Who | Role in the use case | Software role | Technical facts |
|---|---|---|---|
| The university / the lab | Controller: decides why and how the data are processed. | none | The lab chose local inference so that documents stay on its infrastructure. (use-case premise) |
| Supervisor or IT contact | Operates the instance on behalf of the controller; holds the admin account. | `admin` | The first account created becomes admin and sign-up then closes: `routers/auths.py:821-824`, VERIFIED (code); VERIFIED (run R01). |
| PhD students and researchers | Users of the tool, and data subjects (their own chats, drafts, e-mail, usage). | `user` | Admin-created accounts get role `user`: VERIFIED (run R01). New self-signups would get `pending` (`config.py:1748`, VERIFIED (code)), but sign-up is closed after the first user: VERIFIED (run R01). |
| Co-authors, interviewees, survey respondents, third parties named in chats | Data subjects without an account; may not know the data are in the system. | none | Their text sits in A03–A06 (see inventory). |
| Colleague who receives a shared chat | Reader with access granted by the chat owner. | `user` with a grant | A link alone grants nothing; a grant to a user is needed: VERIFIED (run R08). |
| Ollama | Local processing component on lab infrastructure; not a separate organisation receiving data. | external service called over HTTP | Separate container in the official compose: `docker-compose.yaml:2-9`, VERIFIED (doc). Whether it runs on the same host as the web application in the lab: HYPOTHESIS (Q4). |
| Lab IT / host administrator | Whoever can read the server's disks, containers and logs. May be the same person as the admin. | outside the application | See DS1–DS4 in `architecture.md`. Who this is in the lab: HYPOTHESIS (Q5). |

**Role overlaps (stated).**
1. The admin is typically also a supervisor, i.e. the person with power over the careers of the users whose data the admin can read. Whether the admin also has a normal user account: HYPOTHESIS (Q5); the software allows it.
2. The admin account is a normal account with a higher role. One person can act as E1 (user) and E3 (admin) in the diagram.
3. The same human can be user, data subject (as author of the draft) and third party (as co-author in someone else's draft).

## 3. Data inventory

"Retention" means how long the system keeps the data **by itself**. A search of the backend for retention, auto-delete, expiry, purge and prune settings found none that expires chats, files or accounts by age: the only hits are an unrelated knowledge-base file flag (`config.py:992`) and a chat context-compaction percentage (`config.py:2233`) (VERIFIED (code) by search; the absence is a search result, not a proof, see Q9). Data therefore stays until someone deletes it.

"Who can access" is the default configuration. Admin read access to other users' chats is on by default: `ENABLE_ADMIN_CHAT_ACCESS=True` (`env.py:371`) and `ENABLE_ADMIN_EXPORT=True` (`config.py:2112`), VERIFIED (code).

| # | Data (asset) | Purpose | Where stored | Who can access | Retention | Deletion behaviour (observed) | Reference | Tag |
|---|---|---|---|---|---|---|---|---|
| 1 | **Account details** (A01): name, e-mail, role, password hash (bcrypt), optional gender, date of birth, bio, timezone, last-active time | Sign-in, roles | DS1 tables `user`, `auth` | Owner; admin (list of all users with details) | Until the account is deleted | Admin deletes the user: the `user` and `auth` rows and the user's chats are removed; other rows owned by the user stay (see row 15). VERIFIED (run R12) | `models/users.py:142-174`, `models/auths.py:27-34`, `routers/users.py:1062`, `models/users.py:849-863`, `env.py:821` | VERIFIED |
| 2 | **Chat content, primary copy** (A02): every prompt and answer, plus attached file ids | Show history, continue conversations | DS1 `chat.chat` (JSON) | Owner; admin (read by user id, bulk export); users with a share grant (via snapshot, row 4) | No expiry | Owner deletes chat: row removed. Text stays in the SQLite write-ahead file until a checkpoint, then is gone from the main file in the tested SQLite build. VERIFIED (run R10); behaviour of the Docker image's SQLite: HYPOTHESIS (Q6) | `models/chats.py:131-142`, `routers/chats.py:1657-1715` | VERIFIED |
| 3 | **Chat content, second copy** (A02): the same messages as individual rows, with the retrieved passages (`sources`) | Statistics, search, per-message handling | DS1 `chat_message` | Owner; admin; admin analytics route returns messages | No expiry | Removed with the chat. VERIFIED (run R10) | `models/chat_messages.py:130-151`, `routers/analytics.py:125` | VERIFIED |
| 4 | **Shared-chat snapshot** (A06): a frozen full copy of the chat, including retrieved passages | Let others read it | DS1 `shared_chat` | Users with a grant; owner; admin | Until unshared or the chat is deleted | Removed when the chat is deleted. The matching access-grant row is **not** removed. VERIFIED (run R08, R10: grant rows 1→1) | `models/shared_chats.py:25-90`, `routers/chats.py:2049-2135` | VERIFIED |
| 5 | **Share access list and link id** (A07) | Decide who may open a share | DS1 `access_grant`, `chat.share_id` | Owner; admin | As row 4, except the leftover grant | See row 4 | `models/access_grants.py:25,545` | VERIFIED |
| 6 | **Chat title and tags** (part of A02), generated by background tasks when requested by the client | Navigation | DS1 `chat.title`, `chat.meta.tags`, table `tag` (with user id) | Owner; admin | No expiry | Removed with the chat. VERIFIED (run R07, R10). What a real model puts in titles/tags: HYPOTHESIS (Q10) | `utils/middleware.py:4002-4089`, `models/tags.py:18`; defaults `config.py:2338-2342` | VERIFIED |
| 7 | **Uploaded original file** (A03) | Source for answers; user may re-download | DS2 `uploads/{uuid}_{original name}` | Owner; admin; users granted access to the file | No expiry | Deleting the file removes the disk copy and the file row. VERIFIED (run R11). Admin deleting the user leaves it. VERIFIED (run R12) | `routers/files.py:324-488` (name at 367), `storage/provider.py:63-103`, `routers/files.py:1024-1078` | VERIFIED |
| 8 | **Extracted text of the file** (A04), the whole text | Quick display, re-indexing | DS1 `file.data.content` | Owner; admin (route returns it); users granted access | No expiry | Removed with the file row. VERIFIED (run R11). Left behind after user deletion. VERIFIED (run R12) | `routers/retrieval.py:1709-1711`, `models/files.py:18-27` | VERIFIED |
| 9 | **Text chunks, embeddings and chunk metadata** (A05): ~1000-character pieces, number vectors, user id, file name, embedding settings | Find relevant passages | DS3 Chroma collection `file-{id}` in `vector_db/` | Application only; the lab IT with disk access | No expiry | **After file deletion the collection and its text remain.** VERIFIED (run R11). Left after user deletion. VERIFIED (run R12). Cause located in code: `routers/files.py:1053` calls `delete` without ids or filter; `retrieval/vector/dbs/chroma.py:185-202` does nothing in that case | `routers/retrieval.py:1366-1617`, `config.py:1071,1075` (chunk 1000 / overlap 100) | VERIFIED |
| 10 | **Memories** (user-level facts the app may keep), if the user adds them | Personalisation | DS1 `memory`, DS3 collection `user-memory-{uid}` | Owner (admin: not tested) | No expiry | Left after user deletion. VERIFIED (run R12). Automatic creation of memories is off by default: `config.py:434` VERIFIED (code) | `models/memories.py:15`, `utils/memory.py:410` | VERIFIED |
| 11 | **Notes, folders** | Organisation | DS1 `note`, `folder` | Owner (others by grant) | No expiry | Left after user deletion. VERIFIED (run R12) | `models/notes.py:20`, `models/folders.py:22` | VERIFIED |
| 12 | **Session token** (A09) | Stay signed in | Browser cookie (HttpOnly, SameSite=lax, 28 days, no Secure flag) and, per frontend code, browser `localStorage` | The browser's owner; anyone with the token | 4 weeks by default | Cookie expires; no server-side session list was examined: HYPOTHESIS (Q7) | `routers/auths.py:205-218`, `env.py:777-785`, `config.py:2531`; VERIFIED (run R02); `ShareChatModal.svelte:34` | VERIFIED (cookie) / HYPOTHESIS (localStorage use) |
| 13 | **Log entries** (A08): login e-mail, file names, user ids | Operation | DS4: process standard output; optional audit file | Whoever reads container logs | Not managed by the app | Not managed. Default log contains the login e-mail, not chunk or chat text. VERIFIED (run R14) | `models/auths.py:336`, `retrieval/utils.py:337` | VERIFIED |
| 14 | **Audit log** (optional): user id/name/e-mail/role, source IP, request path, bodies at the highest level | Accountability | `audit.log` file | Host access | Off: `AUDIT_LOG_LEVEL=NONE`, and chat paths are excluded by default | No audit file exists in the default run. VERIFIED (run R09) | `env.py:1231-1256`, `utils/audit.py:298` | VERIFIED |
| 15 | **Leftover rows after user deletion** (files, memories, notes, folders, vector collections) | n/a (side effect) | DS1, DS2, DS3 | Admin; host access | Indefinite | See rows 7–11 | `models/users.py:849-863`; VERIFIED (run R12) | VERIFIED |
| 16 | **Temporary-chat text** | One-off chat | Not stored by the server | n/a | n/a | No database rows and no bytes on disk; the text is still sent to Ollama. VERIFIED (run R13) | `utils/chat_id.py:4,15` | VERIFIED |
| 17 | **Whole-database copy** (A10) | Admin export | Created on request | Admin | n/a | `GET /api/v1/utils/db/download` returns the entire SQLite file (729 KB in the test). VERIFIED (run R09) | `routers/utils.py:75` | VERIFIED |

Copies of one document's content on disk in the default setup: the original file (row 7), the full text in the database (row 8), and the chunk text inside the vector database file, where the same chunk text appears three to four times (replay: 3 occurrences of a 194-character file chunk and 4 of a short memory text in `chroma.sqlite3`). VERIFIED (run R06; occurrence count measured in the replay session). Also the text appears in message rows and in share snapshots when retrieved into a chat (rows 2–4).

## 4. Components

See `architecture.md` section 2 for the component list with evidence. Privacy-relevant defaults (all VERIFIED (code) unless marked):

| Setting | Default | Where |
|---|---|---|
| Admin may read any user's chats | on | `env.py:371` |
| Admin may export all chats and download the database | on | `config.py:2112` |
| Admin analytics (users, usage, messages) | on | `config.py:2124` |
| Share chats allowed / public sharing / open sharing | on / off / off | `config.py:1903, 1905, 1909` |
| Temporary chats allowed | on | `config.py:1925` |
| Community sharing button | on | `config.py:2126` |
| OpenAI-compatible connection | on, base URL `https://api.openai.com/v1`, empty key | `config.py:325, 329` |
| Version update check | on (off in offline mode) | `env.py:1212-1213` |
| Forward user info headers to model servers | off | `env.py:997` |
| Telemetry | disabled in the image (`SCARF_NO_ANALYTICS`, `DO_NOT_TRACK`, `ANONYMIZED_TELEMETRY=false`) | `Dockerfile:95-97` (VERIFIED (doc)) |
| Embeddings engine | empty = local SentenceTransformers (model `all-MiniLM-L6-v2`); the tested run used Ollama embeddings by environment setting | `config.py:1009-1020`; run script `pia/verification/run_instance.sh` |
| Retrieved passages per question / chunk size / overlap | 3 / 1000 / 100 | `config.py:975, 1071, 1075` |
| Title, tags, follow-up and retrieval-query generation | on (executed only when the client requests them) | `config.py:2338-2347` |
| Autocomplete generation, automatic memory review | off | `config.py:2376, 434` |
| Session length | 4 weeks | `config.py:2531` |
| Cookie flags | HttpOnly, SameSite=lax, Secure off | `env.py:777-785` |
| Sign-up | closed after the first account | `routers/auths.py:821-824` |
| Code interpreter | on, but runs in the browser with self-hosted files | `config.py:430`, `src/lib/workers/pyodide.worker.ts:27-28` |
| Secret key | empty in compose, so `start.sh` creates `.webui_secret_key` in the app directory, not in the data volume | `docker-compose.yaml:25`, `backend/start.sh:31` |

## 5. Data flows per scenario step

Each block lists: flows (IDs from `architecture.md`), data, where stored, who can access, retention/deletion, evidence, and then a **note of privacy-relevant observations** (HYPOTHESIS, stated without analysis).

### 5.1 Logging in (F1–F4)
- **Data:** e-mail, password (in transit), session token (out). Password stored only as a bcrypt hash.
- **Stored:** DS1 `user`, `auth`; token in browser; DS4 log line with the e-mail.
- **Access:** the user; admin sees account list; host reader sees log.
- **Retention/deletion:** token 4 weeks; accounts until deleted (partly, see 5.7).
- **Evidence:** `routers/auths.py:205-218, 653`, `models/auths.py:336`, `env.py:777-785, 821`; VERIFIED (run R01, R02, R14).
- **Observations (HYPOTHESIS):** O-1.1 the cookie has no Secure flag and the compose file serves plain HTTP; whether the lab adds TLS is unknown (Q3). O-1.2 the first account becomes admin, which means whoever signs up first holds the power (VERIFIED (run R01)); in a lab that is the person who installs it. O-1.3 profile fields such as date of birth exist in the account table; whether they are filled is lab practice (Q5).

### 5.2 Chatting without documents (F5–F9)
- **Data:** every message; the whole chat history is sent to Ollama again on each turn. Up to six calls per turn were seen when background tasks are requested (answer, title, tags, follow-ups, search-query generation, embedding).
- **Stored:** DS1 in two tables (`chat.chat`, `chat_message`); derived title and tags.
- **Access:** owner; admin; nobody else unless shared.
- **Retention/deletion:** until the owner deletes the chat (5.7).
- **Evidence:** `main.py:1146`, `utils/middleware.py:3944, 4002, 4064`, `routers/ollama.py:1196`, `models/chats.py:131`, `models/chat_messages.py:130`; VERIFIED (run R07).
- **Observations (HYPOTHESIS):** O-2.1 the same text exists in at least two tables. O-2.2 title and tags are new data derived from the content, stored with the user id. O-2.3 the frontend also sends both a `history` and a `messages` form of the chat when it creates a chat (`src/lib/components/chat/Chat.svelte:4558-4566`, code reading only). O-2.4 temporary chats leave no server record yet reach Ollama (VERIFIED (run R13)); what Ollama itself keeps is unknown (Q4). O-2.5 whether title/tags reveal sensitive subjects depends on the model (Q10).

### 5.3 Uploading a draft (F12–F17)
- **Data:** file bytes; extracted text; chunk text; vectors; metadata (user id, file name, embedding settings).
- **Stored:** DS2 original; DS1 `file.data.content` full text; DS3 collection `file-{id}`.
- **Access:** owner; admin can read the file record, the extracted text and the raw file (VERIFIED (run R09)); other users get 404 (VERIFIED (run R08, R09)).
- **Retention/deletion:** no expiry; see 5.7.
- **Evidence:** `routers/files.py:324-488, 367, 375, 408`, `routers/retrieval.py:1366, 1549, 1572, 1592, 1617, 1709`, `retrieval/utils.py:1031-1096`; VERIFIED (run R06).
- **Observations (HYPOTHESIS):** O-3.1 one uploaded text is stored in three systems (disk, database, vector store). O-3.2 the upload response returns the absolute server path of the file (VERIFIED (run R06)). O-3.3 the chunk text is sent to Ollama for embedding with no user identity attached by default (`ENABLE_FORWARD_USER_INFO_HEADERS=False`, `env.py:997`; VERIFIED (run R06)). O-3.4 the chunk metadata carries the user id and file name next to the text. O-3.5 interview or survey text is processed exactly like any other file; the software has no notion of special data or of a data subject other than the account owner.

### 5.4 Asking a question about a document (F8–F11, F18–F21)
- **Data:** the question; the whole chat so far; the retrieved passages (about three chunks of up to 1000 characters); title/tag/follow-up prompts.
- **Stored:** DS1 message rows and chat JSON, including the retrieved passages (`sources`); DS4 a log line with file name and user id per retrieval.
- **Access:** as 5.2.
- **Retention/deletion:** the stored passages live as long as the chat.
- **Evidence:** `utils/middleware.py:2084-2202`, `retrieval/utils.py:337, 1358`; VERIFIED (run R07, R14).
- **Observations (HYPOTHESIS):** O-4.1 passages from a document are copied into the chat and so outlive the file: after the file is deleted, the chat still holds them. O-4.2 a share snapshot copies them again (5.5). O-4.3 in the one non-streaming request tried, the passages were not stored (null), in the streaming path they were; the frontend uses streaming by default (HYPOTHESIS, Q7). O-4.4 the retrieval log line contains file name and user id, not text (VERIFIED (run R14)).

### 5.5 Sharing a chat (F22–F25)
- **Data:** a full copy (snapshot) of the chat, including retrieved passages and the ids and names of attached files.
- **Stored:** DS1 `shared_chat`; `chat.share_id`; `access_grant` rows.
- **Access:** nobody by link alone: not logged in → 401; logged in without a grant → 401. A user grant allows reading; an attempt by an ordinary user to grant "anyone" was filtered out (permission off by default); admin can read the share. A granted reader could not open the underlying file or its text (404).
- **Retention/deletion:** until unshared or the chat is deleted; the grant row remains after chat deletion (orphan).
- **Evidence:** `routers/chats.py:114-139, 1276, 2049, 2100, 2135`, `models/shared_chats.py:25-90`, `config.py:1903-1909`; VERIFIED (run R08, R10).
- **Observations (HYPOTHESIS):** O-5.1 the snapshot is a copy: later edits or deletion of the original may not change what the colleague sees; deletion of the chat did remove the snapshot (VERIFIED (run R10)). O-5.2 the snapshot exposes interview passages to the colleague although the colleague cannot open the source file. O-5.3 interviewees have no way to learn that their words were shared. O-5.4 the "share to community" button posts the full chat to openwebui.com when a user clicks it; shown to users with the community-sharing setting on (`ShareChatModal.svelte:49-70, 197-208`, code reading only; Q7).

### 5.6 Admin looking at the system (F26–F29)
- **Data:** everything above.
- **Access/actions seen:** list any user's chats; read any chat; export all chats; read any file record, extracted text and raw file; list all users; usage analytics (per-user counts and tokens); download the whole SQLite file. An ordinary user gets 401 or 404 on each.
- **Logging:** the default server log shows method, path and status code, not who read what; the audit file does not exist by default (`AUDIT_LOG_LEVEL=NONE`, chat paths excluded).
- **Evidence:** `routers/chats.py:784, 1111`, `routers/files.py:606-615`, `routers/analytics.py:85, 125`, `routers/utils.py:75`, `env.py:371, 1231-1256`, `config.py:2112, 2124`; VERIFIED (run R09).
- **Observations (HYPOTHESIS):** O-6.1 admin read access needs no extra step, approval or notification to the user. O-6.2 nothing in the default record shows that an admin read a particular chat. O-6.3 the admin can switch the read access off by configuration (`ENABLE_ADMIN_CHAT_ACCESS`); whether the lab does is unknown (Q11). O-6.4 the host administrator can reach the same data through the disks without any of the application's checks (not an application feature; DS1–DS3 are plain files).

### 5.7 Deleting a chat, a file, a user (F5, F12, F28)
| Action | What the application removed | What remained | Evidence |
|---|---|---|---|
| User deletes a chat | `chat`, `chat_message`, `shared_chat`, `tag` rows | The chat text in the database's write-ahead file until the next checkpoint; the share's `access_grant` row | VERIFIED (run R10) |
| User deletes a file | file row, upload on disk | **Vector collection `file-{id}` with the chunk text**; passages already copied into chats | VERIFIED (run R11, R07) |
| Admin deletes a user | `user`, `auth`, groups membership, the user's chats | The user's files (row, disk copy, text), memories, notes, folders, and the vector collections `file-{id}` and `user-memory-{uid}`, with survey text still readable | VERIFIED (run R12) |
| Temporary chat | nothing was stored | nothing on disk | VERIFIED (run R13) |

- **Evidence in code:** `routers/chats.py:1657`, `routers/files.py:1024-1078 (1053)`, `retrieval/vector/dbs/chroma.py:72, 185-202`, `models/users.py:849-863`, `routers/users.py:1062-1096`. SQLite foreign keys are not switched on (no `PRAGMA foreign_keys` in the backend), so removal relies on explicit delete calls.
- **Observations (HYPOTHESIS):** O-7.1 "deleted" in the interface and "gone from disk" are different states for files and users. O-7.2 an interviewee's right to have their words removed has no function in the application that finds them across chats, files and vectors. O-7.3 whether the Docker image's SQLite physically clears deleted pages the way the tested build did is unknown (Q6).

### 5.8 Outbound connections (F30–F38)
- **Seen on a running instance (egress proxy):** a connection attempt to `api.openai.com:443` once the model list is requested (1 attempt in the replay, 3 in an earlier run with three listings; whether each listing triggers one is unknown, Q1). The request is `GET {base_url}/models`; it carries the (empty) key, no chat data. **No other outbound attempt** during the whole scenario (sign-in, chat, upload, RAG, share, admin, delete). The idle start made none. VERIFIED (run R03, R04).
- **In the code, not triggered in the runs:** version check to `api.github.com` when a signed-in user's browser calls `/api/version/updates` (`main.py:2681-2689`); the licence check contacts `api.openwebui.com` and `licenses.api.openwebui.com` only if a licence key is set (`utils/auth.py:85, 122-126`); a branding lookup at `api.openwebui.com` only if `CUSTOM_NAME` is set (`config.py:199-203`); favicon requests to Google for citation sources whose name starts with `http` (`Citations.svelte:172,188`); full-chat post to openwebui.com on click (`ShareChatModal.svelte:49-70`); webhooks if the admin configures them, carrying actor id, name, e-mail and role (`events.py:737, 1102, 1226`). VERIFIED (code); not exercised.
- **Not tested at all:** the default local SentenceTransformers embedding and the Hugging Face model auto-update (`config.py:1009-1020`): this requires the image and its model files (Q1).
- **Observations (HYPOTHESIS):** O-8.1 a lab that expects "no data leaves the building" has at least one default outbound destination (OpenAI) that is not about its documents. O-8.2 the Dockerfile sets telemetry off (`Dockerfile:95-97`), VERIFIED (doc). O-8.3 `OFFLINE_MODE` disables the update check and Hugging Face access (`env.py:1212-1213`); whether the lab uses it is unknown.

### 5.9 Logs and backups (F4, F21, DS4)
- **Logs:** default log (INFO, standard output) contains the login e-mail and, per retrieval, file name, content hash and user id; no chunk text and no chat text (VERIFIED (run R14); `models/auths.py:336`, `retrieval/utils.py:337`). The uvicorn access line has method, path, status. No audit file by default (VERIFIED (run R09)).
- **Backups:** the backend has no backup function (a search found none). Backups of the volume, if any, are the lab's practice and would copy DS1–DS3 (HYPOTHESIS, Q2).
- **Observations (HYPOTHESIS):** O-9.1 log content is governed by whoever runs the container, not by the application. O-9.2 a backup would hold deleted-in-the-app material for as long as the backup lives (Q2). O-9.3 the share link id is part of a URL, which a reverse proxy may log (Q12).

## 6. Trust boundaries and assumptions

| Boundary | Inside | Assumption made in this analysis | Tag |
|---|---|---|---|
| TB1 users' devices | Browsers, local storage, downloads | Not controlled by lab IT. Users may use private or shared machines. | HYPOTHESIS (Q8) |
| TB2 lab server | Web application, database, uploads, vector store, logs, Ollama container | Controlled by the lab; physical and operating-system access limited to the lab's IT contact; data volume is one named volume `open-webui:/app/backend/data` (`docker-compose.yaml:18`) | VERIFIED (doc) for the volume; the rest HYPOTHESIS (Q4, Q5) |
| TB3 internet | OpenAI, GitHub, openwebui.com, Google favicons | Outside the lab's control; the application sends destinations and, for the community share, a full chat | VERIFIED (code, run R04) |
| Admin ↔ users | Same application, different role | The admin is trusted by the controller but is not a data subject's chosen counterpart; see section 2, overlap 1 | assumption |
| App ↔ Ollama | HTTP, internal Docker network | Not encrypted by the application; internal network assumed | HYPOTHESIS (Q4) |

Other assumptions: default configuration of v0.12.2; a single instance (no Redis, no multiple workers; Redis absent by default, HYPOTHESIS Q13); SQLite and Chroma (the `USE_SLIM` image switches the default vector database to pgvector, `config.py:509`, VERIFIED (code)); local accounts (a university single-sign-on or directory sync would add flows: Q13).

## 7. Big-data angle

**Why volume matters here.** Each uploaded document becomes many stored pieces, and each chat turn writes a new copy of history-bearing text. The lab's data grows quietly and in several systems, which makes later deletion and answering questions such as "where is interviewee P07's text?" harder.

**Measured on the test instance** (synthetic documents of 60 KB of text, 20 documents and 40 chat turns with 1500-character answers; stub embeddings of 16 numbers each; Chroma and SQLite defaults; VERIFIED (run R15), `pia/verification/measure_volumes.py`, results `pia/verification/volumes_result.json`):

| Quantity | Measured |
|---|---|
| Chunks per 60 KB document | 69 (chunk size 1000, overlap 100) |
| Original file on disk per document | about 61 KB |
| Extracted text in the database per document | about 62 KB |
| Vector-store folder per document | about 872 KB with 16-number vectors, i.e. roughly 12.5 KB per chunk. Most of that is the text, metadata and search indexes Chroma keeps in `chroma.sqlite3`, not the vectors. |
| Database growth per chat turn (RAG question with 1500-character answer) | about 22 KB (message rows, chat JSON, tags, sources) |
| Vector growth per chat turn | 0 |
| Fixed baseline | database 770 KB with 372 settings rows, 3 chunks |
| Copies of one chunk's text in `chroma.sqlite3` | 3 to 4 (replay) |

**What a real embedding model adds (assumption, HYPOTHESIS Q9).** With a real model the vector for each chunk is 384, 768 or 1024 numbers (the default local model `all-MiniLM-L6-v2` is named in `config.py:1015`; its size of 384 numbers is general knowledge, not seen in this repo). That is 1.5 KB to 4 KB per chunk of raw numbers, on top of the measured figures.

**Illustrative scale (ASSUMPTIONS, not measurements; arithmetic from the table above):**

| Assumed lab | Documents | Chunks | Original files | Database text | Vector folder (stub vectors) | Chat growth per year | Added by real vectors (384…1024 numbers) |
|---|---|---|---|---|---|---|---|
| Small: 10 users, 50 documents each, 5 chat turns per user per working day | 500 | 34,500 | 31 MB | 31 MB | 436 MB | 221 MB (10,000 turns) | 53–141 MB |
| Larger: 15 users, 100 documents each, 10 turns per user per working day | 1,500 | 103,500 | 92 MB | 93 MB | 1.3 GB | 664 MB (30,000 turns) | 159–424 MB |

**Reading the numbers (description only).** The sizes are small by data-centre standards but the **number of stored copies and places is what grows**: every document sits in three systems, every question adds stored passages, every share adds a snapshot. For the lab's data subjects the relevant count is not gigabytes but the number of chunks (tens of thousands) in which a person's words may sit and which the application does not index by person. Nothing is deleted by age (section 3). The real figures need the real documents and embedding model (Q9).

## 8. Open questions (HYPOTHESES, most important first)

Each has a local check the team can run. "Run" means the verification harness in `pia/verification/`.

| # | Question | Why it matters for the description | Local check |
|---|---|---|---|
| Q1 | Does the real Docker image (default local embedding model, Hugging Face auto-update) make outbound connections that the source run did not? Does every model listing trigger the OpenAI connection or only the first? | The run used Ollama embeddings and `HF_HUB_OFFLINE=1`; it could not exercise the default. | Start the official image behind the egress proxy (`HTTPS_PROXY`), no Ollama embedding override, repeat `run_scenario.py`; read `egress.jsonl`. Repeat model listings and count. |
| Q2 | What backs up the lab's data volume, who holds the copies, for how long? | Deleted-in-app data may live on in backups. | Ask lab IT; `docker volume inspect open-webui`; look for cron, snapshots, cloud sync. |
| Q3 | Is there a TLS-terminating reverse proxy? Is the cookie Secure? Do the proxy's logs record URLs including share ids? | Compose exposes HTTP only. | `curl -I https://<host>`; read proxy config and its access-log format. |
| Q4 | Where does Ollama run (same host? another machine?), and what does Ollama itself store or log from prompts and embedding requests? | Ollama is the one place where all prompts, documents' chunk text and temporary-chat text arrive. | `docker ps`, `docker logs ollama` after a test prompt; inspect the Ollama volume for stored prompts; if remote, add a trust zone to the DFD. |
| Q5 | Who is the admin and who has shell access to the host? Does the admin also use the tool as a normal user? Which profile fields do accounts really hold? | Section 2 role overlaps and TB2 assumptions. | Interview the lab contact; `getent group docker`; list accounts via `/api/v1/users/all` in a test copy. |
| Q6 | Does the Docker image's SQLite physically clear deleted pages (`secure_delete`)? When is the write-ahead file checkpointed? | Sandbox SQLite had `secure_delete=1`. | `docker exec open-webui python -c "import sqlite3;print(sqlite3.sqlite_version, sqlite3.connect(':memory:').execute('pragma secure_delete').fetchone())"`; repeat R10 against the container's data directory. |
| Q7 | Browser behaviour: token kept in `localStorage`, the update-check call, favicon requests, community-share button, streaming default and what it stores. | The frontend was not run; claims are from code reading. | Run the image, open it in a browser with developer tools network tab (or an egress proxy), repeat the scenario by hand, record requests and Application → Local Storage. |
| Q8 | Which devices do users use (shared machines)? Do browsers cache chats? | TB1 assumption. | User survey; check what the frontend persists in the browser. |
| Q9 | Real chunk counts, embedding size and storage per document with the lab's real documents and model; whether any age-based deletion exists in a setting we missed. | Section 7 numbers are from synthetic data; the absence of retention is a search result. | Re-run `measure_volumes.py` with real embeddings; read the admin settings page; re-grep after upgrading. |
| Q10 | What do real titles and tags (and memories, if used) contain for sensitive subjects? | Derived data depends on the model. | Run with the lab's model on dummy sensitive text; read `chat.title`, `tag`. |
| Q11 | Did the lab change `ENABLE_ADMIN_CHAT_ACCESS`, `ENABLE_ADMIN_EXPORT`, audit level, sharing settings, or `OFFLINE_MODE`? | Defaults decide the admin power described in 5.6. | Environment of the container (`docker inspect open-webui`), the admin settings pages, and the lab's compose file. |
| Q12 | Do reverse-proxy or host logs record share URLs, user names or IPs? | Share id sits in a URL. | Read proxy and host log configuration. |
| Q13 | Does the lab use university single sign-on, directory sync (SCIM), Redis, PostgreSQL or the slim image? Does it use knowledge-base collections or notes at scale (not exercised)? | They change account data flows, storage and file handling. | Read the lab's compose and environment; repeat the scenario through the knowledge-base path. |

## Appendix A — Runtime evidence index

Reproduce: start a fresh instance with `pia/verification/run_instance.sh <workdir> <repo> <python>` (set `STUB_REPLY_CHARS=1500`), then `python pia/verification/run_scenario.py <workdir>`. The latest output is in `pia/verification/last_run_output.txt`. Helper scripts: `inspect_state.py` (what is on disk and where a text marker survives), `counts.py`, `measure_volumes.py`, `stub_ollama.py`, `egress_proxy.py`, `scenario_common.py`. Application code is not modified. Caveats: from-source run; API only; stub model; Hugging Face offline; synthetic markers.

| ID | What was checked | Observed |
|---|---|---|
| R01 | First signup, later self-signup, admin-created users | First user = admin; later signup 403; admin-created users have role `user` |
| R02 | Session cookie | HttpOnly; SameSite=lax; Max-Age 2,419,200 s (28 days); no Secure flag |
| R03 | Idle start | Database tables empty except version and 372 settings rows; no outbound attempts; no Ollama calls |
| R04 | Outbound attempts after model listings | `CONNECT api.openai.com:443` only (replay: 1 attempt; earlier run: 3 attempts for 3 listings) |
| R05 | Models visible to an ordinary user | 0 before the admin grants access, 1 after |
| R06 | Upload of a small text file | Plain text in `uploads/`, in `file.data.content`, in the vector store; embed request to Ollama carries the chunk text; response contains the absolute server path |
| R07 | One RAG turn with title/tags/follow-up requested | 6 calls to Ollama (`/api/chat`, `/api/embed`), passage text in the answer prompt; stored message rows with sources; 2 tag rows; generated title |
| R08 | Sharing | Link without login 401; user without grant 401; "anyone" grant by ordinary user not stored; granted user reads snapshot with passages; same user 404 on the file and its text; admin 200 |
| R09 | Admin and ordinary user on 9 routes | Admin 200 on all (chat list, chat, export all, file record, text, raw file, users, analytics, database download of 729,088 bytes); ordinary user 401/404; no audit file; no log line names the admin |
| R10 | Chat deletion | All four row types removed; text in write-ahead file until checkpoint, absent from the checkpointed main file (tested build); share grant row left (1 → 1) |
| R11 | File deletion | 200; upload gone; vector collection with the text still present |
| R12 | Admin deletes a user | Rows left in `memory`, `folder`, `file`, `note`; vector collections `file-{id}` and `user-memory-{uid}` hold text; upload on disk |
| R13 | Temporary chat | No chat rows, no bytes on disk, 1 request to Ollama |
| R14 | Default log content | Contains login e-mail; no chunk text; no chat text |
| R15 | Volumes | See section 7 (`measure_volumes.py`, `volumes_result.json`) |
