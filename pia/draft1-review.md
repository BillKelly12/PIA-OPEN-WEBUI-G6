# Review of Group 6's 1st draft (and how to turn it into the 2nd draft)

Reviewed: `Privacy_and_Big_Data2.pdf` (8 pages, Oct 2026), against (a) the official guidelines (`Guidelines for Written Report v11`), (b) our own use case and rules, (c) the code at commit `6a18585` and the Package 1 runs (`pia/data-flow-analysis.md`, R01–R15).
Tags as before: **VERIFIED** = seen in code or in a run (reference given), **HYPOTHESIS** = not yet seen.

## 0. Verdict in six lines

1. The draft is a good **first** draft: honest hook (the "fully offline" claim), default-settings focus, several real findings (admin power, feedback copies, memories).
2. It analyses **Open WebUI in general**, not **our lab use case**. Interviewees, co-authors and students as data subjects are absent, and several items concern setups our lab does not have (external model providers, web search).
3. Its **10 issues are not prioritised**, only 3 have a GDPR article, and 4 are weak or out of scope (7, 8, 9, and 6 as written).
4. It **misses the strongest findings** that our runs produced: deleted files and deleted users leave their text in the vector store; admin reads leave no trace; retrieved passages are copied into chats and share snapshots.
5. A good part of the page budget goes to **model behaviour** (Figure 1, issue 9). The scope excludes model choice and Rule 5 forbids tests that depend on model output.
6. The guidelines ask for tests run by "the relevant testing framework of the project". The draft promises tests but names no framework, and the repository has no backend test suite today.

## 1. Draft vs. the official requirements

| Requirement (guidelines) | Draft | Status | What to do |
|---|---|---|---|
| Part 1: functionality, stakeholders, data and purpose, design choices, ≥1 abstract architecture figure, citations, explicit assumptions | All present in short form | Partly | Re-aim at the use case; make assumptions explicit (we have them in `data-flow-analysis.md` §6) |
| Part 1 stakeholders: overlaps of roles | One sentence | Weak | Use our §2 (controller, admin = supervisor, data subjects without an account) |
| Part 2 starts with a threat model **derived from the architecture diagram**: information at risk, adversary, trust assumptions incl. boundaries | Generic lists; no assumptions; boundaries not drawn | Weak | Derive it from our DFD (trust zones TB1–TB3) |
| Issues prioritised with **your own criteria** | None stated | Missing | Define 3 criteria (§4) |
| Every security issue linked to a privacy issue | Items 6, 7, 8, 9 are not | Missing | Drop or reframe (§3) |
| ≥2 issues with **automated tests** (fail until fixed) | Promised | Missing | §6 |
| Part 3: recommendations with cost-benefit, architecture adapted, implement fixes for a top grade | Not started (fine for draft 1) | Open | §5 and §6 |
| Originality, "interesting insights", a concrete application | Hook is original; content is generic | Partly | Our big-data angle and the deletion findings are the originality |
| Length (draft 1: 500–1200 words + figures) | About 1,300 body words | OK | Draft 2 allows 2,000–3,000 |

## 2. What to keep (the draft is right, and sometimes ahead of us)

- **"Fully offline" as the question to test.** The README says the platform is "built to run entirely offline" (`README.md:13`) and documents `HF_HUB_OFFLINE=1` as the way to stop model downloads (`README.md:226-231`). So offline operation is something the lab has to *switch on*, not a default. This is a sharper framing than "contradiction".
- **Admin visibility by default.** VERIFIED: chat access `env.py:371`, export `config.py:2112`, workspace-content bypass `config.py:2116-2121`, analytics `config.py:2124`. Run R09 confirms admin reads, export and a 729 KB database download; ordinary users get 401/404.
- **Answer ratings keep a copy of the conversation (issue 4).** I missed this in Package 1. VERIFIED in code: the `feedback` table has a `snapshot` column (`models/feedbacks.py:28`), the browser sends the whole chat in it (`src/lib/components/chat/Messages/ResponseMessage.svelte:511`), rating is on by default (`config.py:2128`), and nothing in the chat-delete path touches feedback (no `Feedbacks` call in `routers/chats.py`, `models/chats.py`, `models/users.py`). The admin can export all feedbacks (`routers/evaluations.py:354`). It is **not yet confirmed at runtime**; it becomes our first test.
- **Embedding-model check at startup (issue 8).** VERIFIED: `main.py:716` loads the embedding model at start; with the default engine, `retrieval/utils.py:1732-1745` allows a network check unless offline mode is on. True, but see §3 for why it is a weak finding.
- **Honest limits** ("full LINDDUN will follow") and the build notes (memory use, versions) are useful; keep one line of them.

## 3. Problems, most important first

### 3.1 The draft analyses the product, not the use case
Figure 2 and Figure 3 draw red arrows to model providers, web search and document-reading services; issue 7 is "external providers receive every message". In our lab, inference is local and web search is off (`config.py:1168`). The people who matter most are missing: interviewees, survey respondents and co-authors, who are in the documents but not in the system.
**Fix:** one stakeholder figure with three groups (controller side: university/lab, supervisor-admin; users: PhD students; data subjects without account: interviewees, co-authors). Remove providers and web search from the default picture, or grey them as "off in this use case".

### 3.2 The ten issues: triage

| # | Draft issue | Verdict | Reason and evidence | Action |
|---|---|---|---|---|
| 1 | Admin chat access on by default (Art. 25) | **Keep** | VERIFIED `env.py:371`, run R09 | Merge 1, 2, 3, 10 into one finding "admin sees everything by default" and add the missing point: the default log does not show who read what (R09, `AUDIT_LOG_LEVEL=NONE` `env.py:1246`) |
| 2 | Export and database download | **Merge** into 1 | VERIFIED `config.py:2112`, R09 | — |
| 3 | Admin bypasses access control on workspace content | **Merge** into 1 | VERIFIED default `config.py:2116-2121`; knowledge-base path not exercised | Mark runtime part HYPOTHESIS |
| 4 | Chat deletion keeps copies saved with ratings (Arts. 5(1)(e), 17) | **Keep, make it test #1** | Code VERIFIED (see §2); runtime pending | Note it only affects *rated* messages |
| 5 | Account deletion keeps memories and feedback | **Keep and extend** | VERIFIED memories (R12). R12 also found files, notes, folders, uploads and vector collections left behind. The draft shows only half of the problem | Merge with 4 into "deletion does not delete" |
| 6 | One unencrypted SQLite file, "recoverable deleted chats" | **Reframe or drop** | A security statement with no stated harm. "Recoverable" is overstated: after chat deletion the text stayed only in the write-ahead file until a checkpoint, then was gone from the main file in the tested build (R10). Docker image behaviour: HYPOTHESIS (Q6) | Move to Part 3 as a hardening option (disk encryption); keep only "deleted ≠ erased until checkpoint" |
| 7 | Admin-configured external providers get every message | **Drop** | Out of the use case; no code path to show | Replace with the real default-egress finding below |
| 8 | Hugging Face check at startup contradicts "offline" | **Downgrade** | The request carries no user content (the draft says so itself), and the project documents `HF_HUB_OFFLINE`. Harm is limited to the server's address and model name reaching a third party | Keep as one sentence under "offline is opt-in"; test only with the Docker image (Q1) |
| 9 | App-added tool descriptions cause off-topic answers | **Drop** | Model quality, not privacy; the cause in Figure 1a is stated as fact but is a HYPOTHESIS; out of scope (model choice) | Remove Figure 1a–d narrative |
| 10 | Admin analytics show names, e-mails, counts | **Merge** into 1 | VERIFIED `config.py:2124`, R09 | — |

### 3.3 Findings the draft does not have (from Package 1)

| New candidate | Evidence | Why it matters to a person |
|---|---|---|
| File deletion leaves the text chunks in the vector store | VERIFIED R11; cause `routers/files.py:1053` calls `delete` with no id or filter and `retrieval/vector/dbs/chroma.py:185-202` then does nothing | An interviewee's words stay searchable after the user "deleted" the transcript |
| User deletion leaves files, notes, folders, memories and their vectors | VERIFIED R12; `models/users.py:849-863` | A PhD student leaves the lab; their survey data stays on the server with no owner |
| Admin reads are invisible | VERIFIED R09 (no actor in default log, no audit file) | No accountability for the most powerful role over students' data |
| Retrieved passages are copied into chats and share snapshots | VERIFIED R07, R08 | Interview text lives on in places the file deletion never reaches; a colleague can read passages of a knowledge base they cannot open (R08, test B7); a file stored on the chat message is readable through the share by design |
| Share grant row outlives the deleted chat | VERIFIED R10 (1 → 1) | Small, but shows the same pattern (orphan data) |
| `api.openai.com` is contacted by default | VERIFIED R04 (1 attempt; no chat data in the request) | Weaker as a harm (no documents leave) but it contradicts the lab's "nothing leaves" premise |
| Nothing expires by age | VERIFIED by search only (`data-flow-analysis.md` §3) | Storage limitation depends entirely on people remembering to delete |
| Volume: 69 chunks per 60 KB document, 3–4 copies of each chunk text in the vector file, 22 KB per chat turn | VERIFIED R15 | The big-data angle: many small copies per person, none indexed by person |

### 3.4 Claims that need a correction or a reference
- Table 1, "Memories … recorded from conversations": automatic memory review is **off** by default (`config.py:434`). By default the user adds them. Say so.
- Table 1, "API keys": the feature is off for users by default (`config.py:1952`). Remove, or mark "off".
- Section 3 "156,000 stars, 850 contributors": adds nothing to the privacy argument; cut (about 25 words saved).
- Reference [9] points to a whole directory for many claims. Replace with **permalinks at the commit** with line numbers, for example `github.com/open-webui/open-webui/blob/6a18585/backend/open_webui/env.py#L371`, and tag each claim VERIFIED/HYPOTHESIS (Rule 1).
- Introduction: the quotation is accurate but incomplete. OpenAI wrote that "while unlikely, we cannot rule out that de-identified data derived from their usage of our products helped improve our models", and told the New York Times it was "impossible" for the prompts of the last two months to have influenced the system (as reported by [Smithsonian Magazine](https://www.smithsonianmag.com/smart-news/ai-may-have-solved-a-longstanding-math-problem-with-a-million-dollar-prize-it-ignited-a-controversy-over-who-gets-credit-180989472/)). Add "while unlikely" or a reader will say it is one-sided. Training is out of scope: use the case as one-sentence motivation and then state the exclusion.

### 3.5 Model-dependent material
Section 4 and Figure 1 use three machines and three models (1B, 3B, 0.5B) to show odd answers. The scope says the model is only "the tested configuration", and Rule 5 says tests must not depend on model output. **Fix:** keep one screenshot of the instance running (the guidelines ask for that, nothing more), name one tested configuration, move the rest to an appendix or remove.

### 3.6 Figures
- Figure 3 is a box diagram, not a data-flow diagram. It has no trust boundaries inside the machine, no Ollama as its own container, no logs, no share snapshots, no admin path, and it shows off-by-default services as if they were part of the build.
- **Fix:** use `pia/architecture-dfd.svg` (Package 1) as the Part 1 / Part 2 figure and `pia/architecture-components.svg` as the simple "abstract" figure the guidelines ask for in Part 1.

### 3.7 The threat model is generic
"Chats containing health, work or personal details" could be any chat tool. Tie *information at risk* to our inventory (`data-flow-analysis.md` §3): interview transcripts, survey free-text, unpublished drafts, shared snapshots. Give each adversary a **capability and a motive**: the supervisor-admin (can read everything, has a stake in students' work), a granted colleague (reads passages, not files), a former member (account deleted, data left), a person with the disk or a backup. State **trust assumptions** explicitly: the host and Ollama are trusted, the network is not (HTTP only, `docker-compose.yaml:21-22`), browsers are untrusted.
On LINDDUN: a full per-element analysis is heavy. A practical alternative is to tag each finding with its LINDDUN category (for example Data disclosure, Detecting, Non-compliance, Unawareness) and say that a full pass was done on the DFD's 9 processes in a table in the appendix.

### 3.8 Tests: the framework gap
The guidelines say tests must be runnable by "the relevant testing framework of the selected project". In this repository no backend test files were found (search for `test_*.py` and a `test` folder under `backend/`; only `pytest-asyncio` as a dev dependency, `pyproject.toml:207`; front end uses vitest and Cypress, `package.json:20-21`). **Recommendation:** a `pytest` suite under `backend/open_webui/test/` that calls the HTTP API of a locally started instance and inspects the database and vector store. This is exactly what `run_scenario.py` already does, so we can port R10–R12 and the feedback check into pytest with fixtures.

## 4. Prioritisation criteria (the draft has none)

Proposal, three criteria, scored low/medium/high, plus one rule:
1. **Who is affected:** only the user, other group members, or people with no account (interviewees, co-authors).
2. **Reversibility:** can the harm be undone (e.g. data deleted later) or not (e.g. text already read or copied).
3. **Default exposure:** present out of the box, or only after a deliberate setting.
Rule: a finding that affects people with no account **and** is on by default is "high" unless a mitigation is one configuration switch.

## 5. A better set of findings (options, per Rule 6)

| Option | Findings | Pros | Cons |
|---|---|---|---|
| **A. Deletion and retention** | F1 file deletion leaves chunks; F2 user deletion leaves data (files, memories, notes, vectors, feedback); F3 chat deletion leaves rated copies | Cleanest tests (fail now, pass after fix); direct Art. 17 and 5(1)(e) link; unique to our runs | Does not cover the supervisor-power story |
| **B. Admin power** | F4 default admin read, export and database download; F5 no trace of admin reads; F6 workspace bypass | The power imbalance the course cares about; all VERIFIED | Fix is mostly configuration, so less "interesting" to implement; some of it is a legitimate design choice (moderation) |
| **C. What leaves the lab** | F7 OpenAI default contact; F8 embedding-model check; F9 community-share button | Tests the "fully offline" hook directly | Weak harm (no documents leave); needs the Docker image and a browser for part of it |

**Recommendation:** A as the core (3 findings, 3 tests, implemented fixes), B as the second block (F4+F5 merged, 1 test on the audit trail, configuration + code option), and C reduced to one paragraph that answers the offline question. This gives about 5 findings that are specific, testable and tied to people.

First cut of the register (severity per §4; articles are candidates for the team to confirm with the legal slides):

| ID | Data flow | Privacy harm | GDPR | Test (API/data level) | Mitigation | Sev. |
|---|---|---|---|---|---|---|
| F1 | F12→P3→DS3 (upload then delete) | Interviewee text stays searchable after deletion | 17, 5(1)(e) | Upload a file with a marker, delete it, expect no vector collection `file-{id}` (fails now, R11) | Delete the collection by name when a file is deleted | High |
| F2 | P6→DS1/DS2/DS3 (user deletion) | Departed member's data orphaned | 17, 5(1)(e) | Create user with file, memory, note, feedback; delete user; expect no rows, files or collections for that id (fails now, R12) | One cascade routine used by user deletion | High |
| F3 | P2→DS1 (rating, then chat delete) | Full chat copy kept in `feedback.snapshot` | 17, 5(1)(e), 5(1)(c) | Post feedback with a snapshot, delete the chat, expect the marker gone from `/evaluations/feedbacks/all/export` (fails now, code VERIFIED, run pending) | Store a message id only, or delete feedback with the chat | Medium–High |
| F4 | P6 (admin reads, export) | Supervisor can read students' chats and take the whole database, by default | 25, 5(1)(a), 5(1)(f) | Default config: admin reads another user's chat and downloads the database (passes the "can read" check now; the test asserts it should not happen without an explicit setting) | Secure defaults, or break-glass access with notification | High |
| F5 | P6→DS4 | Reads leave no trace | 5(2), 32 | Admin reads a chat; expect an audit record naming admin and target (fails now, R09) | Turn on audit level for chat routes | Medium |

## 6. Plan to Nov 15 (upload Nov 15, session Nov 16)

| By | Who | Output |
|---|---|---|
| Oct 31 | All four | Agree findings (Option A+B+C-lite) and criteria; commit `pia/` to the fork |
| Nov 5 | Code pair | `pytest` skeleton, F1 and F2 tests failing on current code, screenshot of a failing run |
| Nov 8 | Report pair | Part 1 rewritten (≤1,500 words) from `architecture.md` and `data-flow-analysis.md` |
| Nov 11 | Code pair | F3 test; first fix for F1 (small change), test passing |
| Nov 12 | Report pair | Part 2: threat model, register, test descriptions (≤2,500 words) |
| Nov 14 | All | Merge, word count (2,000–3,000 for draft 2), references as permalinks, upload |

Suggested word budget for draft 2 (about 2,800): Part 1 900, threat model 450, findings and tests 1,000, recommendations (outline only) 300, references and figures extra.

## 7. What I would not change

The title, the Group 6 framing, the build notes, the "default configuration" assumption, and the honesty about what is not yet tested. Keep that tone.
