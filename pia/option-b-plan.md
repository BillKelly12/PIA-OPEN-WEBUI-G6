# Option B — the lab can also use an external model: issues, techniques, tests

Decision (Oct 28): extend the use case. The lab runs Ollama locally by default **and** can connect an OpenAI-compatible external model. Open WebUI supports this natively: the OpenAI connector is on by default with an empty key (`backend/open_webui/config.py:325,329`, run R04), and models are granted per user by the admin (run R05).
Scope wording to settle: our own deployment does not train (out of scope); what the provider keeps or trains on is an **assumption we cannot test**, handled by contract (HYPOTHESIS).
Tags: VERIFIED (code `path:line` / run R##), HYPOTHESIS. LINDDUN categories (lecture 5) in brackets.

## 1. Privacy issues (what can go wrong)

| ID | What goes wrong | Evidence | LINDDUN | GDPR (candidate) |
|---|---|---|---|---|
| B1 | **Every chat turn sends the whole chat plus the retrieved document passages to the provider.** Interview text reaches a third party the interviewees never heard of. | **VERIFIED (test B1, 29 Oct):** with a scripted external provider recording requests, the chat request contained the interviewee's name, e-mail and phone from the retrieved passage. Also VERIFIED for the local route (R07). | Disclosure of information; Unawareness | 5(1)(b),(c), 13/14, 28 |
| B2 | **If the admin sets external embeddings, every chunk of every upload goes out at upload time**, even when chats stay local. | VERIFIED code: `retrieval/utils.py:891-905` posts `{'input': texts}` to the configured endpoint. Default engine is local (`config.py:1009`). **VERIFIED (test B2/B4, 29 Oct):** with the OpenAI embedding engine configured, the provider received the identifiers at upload. | Disclosure | 5(1)(c), 28, Ch. V |
| B3 | **Background tasks follow the chat model.** Title, tags and follow-ups are extra calls that carry the whole chat to the provider unless a task model is set. | VERIFIED code: `utils/task.py:17-28` (external chat model → `TASK_MODEL_EXTERNAL` only if set, otherwise the chat model itself); default empty `config.py:2212`. **VERIFIED (test B3, 29 Oct):** with title, tags and follow-up generation on and no task model set, 3 background requests reached the external provider, each carrying the name and e-mail typed in the chat. | Disclosure; Non-compliance | 5(1)(c), 25 |
| B4 | **No per-document or per-chat rule.** Nothing found that stops a user sending a file marked "interview" to the external model; the only gate is per model (admin grants) and the model's `connection_type` (`utils/task.py:21`). | HYPOTHESIS (search for redaction/local-only features found nothing relevant; absence is a search result). | Non-compliance; Unawareness | 5(1)(b), 25 |
| B5 | **Identity can travel with the data.** If `ENABLE_FORWARD_USER_INFO_HEADERS` is turned on, name, e-mail and role go to the provider with each request. | VERIFIED code: default off `env.py:997`; used in `routers/openai.py:104` and `retrieval/utils.py:899-900`. | Identifying; Linking | 5(1)(c), 25 |
| B6 | **Provider side: retention, training, location.** Outside what we can observe. Legal lecture example: the Italian authority's order against ChatGPT (lawfulness, transparency, accuracy). | HYPOTHESIS by design. | Non-compliance | 28, 44–49, 5(1)(a) |
| B7 | **Sharing a chat discloses retrieved passages the colleague cannot otherwise open.** Narrowed after checking the code: a file stored on the chat message is readable through the share by design (`utils/access_control/files.py`); passages from a knowledge base the colleague cannot open are not. | **VERIFIED (test B7, 29 Oct),** knowledge-base case. R08's wording was too broad. | Disclosure | 5(1)(f), 25 |
| B8 | **Model-derived personal data** (titles, tags, memories) is created and stored; with an external model it is created by the provider. | VERIFIED R07 (stored); provider part HYPOTHESIS. | Detecting; Unawareness | 5(1)(a), 15 |

Easy-fix findings (deletion, admin visibility, audit log) move to a short section **after** the threat model, as the teacher asked. They stay our two mandatory tests with implemented fixes.

## 2. Technologies from the course, and where they fit

| Technique (source) | Fit for B1–B6 | Verdict |
|---|---|---|
| **Pseudonymisation / redaction gateway** (legal lecture, slide 17: pseudonymised data is still personal data) | Strip names, e-mails, identifiers from prompts and chunks before they leave; keep the mapping locally; restore in the answer. | **Implement.** Cheapest real reduction of B1–B3. Still personal data, so contract and transfer rules remain. |
| **Routing policy** ("local only" mark for files/chats; external model blocked or rerouted) | Closes B4; also sets `TASK_MODEL_EXTERNAL` to a local model for B3. | **Implement**, together with the gateway. |
| **Differential privacy** (lecture 3: suited to numeric data; not for text, images) | Not for prompts or documents. Fits aggregate usage statistics only, and with about 10 users the noise would swamp the counts. | **Discuss, reject for the main path.** Keep one paragraph on admin analytics. |
| **Secure multiparty computation / linear secret sharing** (lecture 4) | Split the input over non-colluding parties so none sees it. Cost grows with multiplications and the function must avoid data-dependent branching; LLM inference is far outside that today. | **Discuss, reject**, with the lecture's own cost criteria. |
| **Fully homomorphic encryption** (lecture 4; lecture 7 comes later) | Provider computes on ciphertext. Noise budget and slow bootstrapping make full LLM inference impractical (my general knowledge, check lecture 7). A narrower idea: similarity search over encrypted embeddings. | **Discuss, reject for inference;** possible "future work" for retrieval. |
| **Zero-knowledge proofs** (lecture 4, "confidential and verifiable telemetry": redact by policy and prove it was done) | Direct analogy: the lab redacts by policy; a proof lets an auditor check it without seeing the data (accountability, Art. 5(2)). | **Discuss as the most original idea;** do not implement. |
| Encryption in transit | HTTPS to the provider is standard; it does not protect against the provider itself. | Mention. |
| Federated learning (lecture 8) | Needs training; out of scope. | One line. |
| Trusted execution environments / confidential computing (not in the course) | Realistic provider-side option. | Mention as outside the course. |

Part 3 must show cost-benefit: gateway + routing are cheap and testable; DP, MPC, FHE, ZKP are explained and rejected or deferred with reasons. That is the "nuance" the guidelines ask for.

## 3. Testing (Rule 5: no dependence on model output)

**Update 29 Oct:** the official Open WebUI test suite (separate repository `open-webui/tests`, pytest) already contains a scripted OpenAI-style provider that records every request, so we did not build our own stub. Our tests live in `pia/tests/privacy/` and run on that harness with `bash pia/tests/run.sh` (see `pia/tests/README.md`). The table below is the original plan; the implemented tests are in the README.

| Test | Asserts | Fails now? |
|---|---|---|
| T1 provider payload | Upload a transcript with a marker name and e-mail, ask a question through an external model; the stub's recorded body must not contain the marker. | Expected yes (B1, to confirm) |
| T2 task routing | For the same chat, no title/tag request reaches the provider. | Expected yes (B3, to confirm) |
| T3 embeddings | With a file marked "local only", no `/v1/embeddings` request reaches the provider. | Expected yes (B2, B4) |
| T4, T5 (easy fixes) | File deletion and user deletion leave nothing in the vector store (R11, R12). | Yes, verified |

Optional extras (evidence, not pass/fail):
- **LINDDUN** (lecture 5) is the threat-modelling method: tag each finding with its category; the draft already promised it.
- **Microsoft Presidio** (open-source personal-data detector) as an oracle that scans the stub's captured payloads and counts personal-data entities. Not verified here; check before adopting.
- **Giskard** (v3 scan): needs an LLM provider and key, defaults to OpenAI's `gpt-4o-mini` as judge; privacy detectors unconfirmed ([PyPI](https://pypi.org/project/giskard)). Use synthetic data only and treat results as measurements.

## 4. Next steps (code pair, about 3–4 days)
1. ~~Extend `stub_ollama.py` to the OpenAI protocol~~ Done differently: the official harness provides the external-provider stub; B1–B3 are now VERIFIED by tests.
2. Check whether a filter Function can modify messages before they leave (`routers/functions.py:207` shows functions are admin-created; `utils/filter.py` handles filters): HYPOTHESIS until read.
3. Write T1–T5 as pytest; screenshot a failing run for the draft.
