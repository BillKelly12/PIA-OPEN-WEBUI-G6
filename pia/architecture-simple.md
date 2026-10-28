# Open WebUI — Simplified diagrams for the report

Five small views instead of one large one. Read them in order. Each has a caption that says what is VERIFIED (code line or run R##, see `data-flow-analysis.md` Appendix A) and what is not.

**Notation (course slides 45–48):** rectangle = person or outside system (E), rounded box = process (P), cylinder = data store (DS), arrow = data flow, red dashed box = trust boundary (TB1 users' devices, TB2 lab server, TB3 internet; data crossing a box edge leaves or enters the lab's control). Figures 3 and 4 are *views* of the detailed level-1 diagram (`architecture-dfd.svg`): same IDs, other elements left out on purpose. Figure 5 is a map, not a DFD.

| Figure | Answers the question | Detail lives in |
|---|---|---|
| 1 Who | Who has power over whose data? | `data-flow-analysis.md` §2 |
| 2 System | What is in the system and what leaves it? | `architecture.md` §2–3 |
| 3 Upload and ask | How many copies of a document exist? | §5.3, §5.4, §7 |
| 4 Share and admin | Who can read what, and is it recorded? | §5.5, §5.6 |
| 5 Deletion | What is left when something is deleted? | §5.7 |

## Figure 1 — Who is involved

![Figure 1 — Who is involved](figures/s4-stakeholders.png)

Four groups instead of a dozen boxes. The red arrow is the power gap: the admin, who is often also the students' supervisor, can read every chat and file by default (VERIFIED, `env.py:371`, run R09). The dotted arrows show the people who are in the documents without an account.

<details><summary>Mermaid source</summary>

```mermaid
---
config:
  layout: elk
---
flowchart TB
  subgraph G1["Decide and run"]
    U["University / lab (controller)"]
    A["Supervisor or IT contact (admin), often also the students' supervisor"]
  end
  subgraph G2["Use the tool"]
    S["PhD students and researchers"]
    C["Colleague with share access"]
  end
  subgraph G3["In the documents, no account, may not know"]
    I["Interviewees, survey respondents"]
    CA["Co-authors, people named in drafts"]
  end
  subgraph G4["Outside the lab"]
    M["Open WebUI maintainers, plugin authors"]
  end
  U -->|"appoints, sets rules"| A
  A -->|"can read all chats and files by default"| S
  S -->|"share a frozen copy"| C
  I -.->|"their words are uploaded"| S
  CA -.->|"their text is uploaded"| S
  M -->|"software and updates"| A
  linkStyle 1 stroke:#d00,stroke-width:3px
```
</details>

## Figure 2 — The system in one picture (context level)

![Figure 2 — The system in one picture (context level)](figures/s0-context.png)

One server, one local model, one group of stores, three kinds of people, and the internet. Red = admin reach. Orange = connections to the internet; the one made by the server carries no documents (VERIFIED, run R04); the one from the browser carries a full chat but only when a user clicks (VERIFIED in code, `ShareChatModal.svelte:49-70`, not run).

<details><summary>Mermaid source</summary>

```mermaid
---
config:
  layout: elk
---
flowchart LR
  subgraph TB1["TB1 · Users' devices"]
    E1["E1 Researcher"]
    E2["E2 Colleague with share access"]
    E3["E3 Admin (supervisor / IT)"]
    P9("P9 Browser: share-to-community button")
  end
  subgraph TB2["TB2 · Lab server"]
    P0("P0 Open WebUI server")
    P7("P7 Ollama, local model")
    DS[("DS Lab stores: database, uploads, vector store, log")]
  end
  subgraph TB3["TB3 · Internet"]
    E4["E4 OpenAI, GitHub, openwebui.com, Google icons"]
  end
  E1 -->|"login, chats, files"| P0
  P0 -->|"answers, own history"| E1
  E2 -->|"link + login"| P0
  P0 -->|"frozen copy of a chat"| E2
  E3 -->|"admin requests"| P0
  P0 -->|"any chat, file, user list, whole database"| E3
  P0 <-->|"all stored data"| DS
  P0 <-->|"prompts + passages / answers + number codes"| P7
  P0 -->|"model-list request, version check (no documents)"| E4
  E1 -->|"click"| P9
  P9 -->|"full chat, only on click"| E4
  linkStyle 5 stroke:#d00,stroke-width:3px
  linkStyle 8 stroke:#e08000,stroke-width:2px
  linkStyle 10 stroke:#e08000,stroke-width:2px
  style TB1 fill:none,stroke:#d00,stroke-width:2px,stroke-dasharray:6 4
  style TB2 fill:none,stroke:#d00,stroke-width:2px,stroke-dasharray:6 4
  style TB3 fill:none,stroke:#d00,stroke-width:2px,stroke-dasharray:6 4
```
</details>

## Figure 3 — Upload a draft, then ask a question

![Figure 3 — Upload a draft, then ask a question](figures/s1-upload-ask.png)

Shows the **four copies** of the same document text on the server: original file, full text in the database, pieces in the vector store, and passages saved inside the chat (VERIFIED, runs R06 and R07). The local model receives the text pieces and the whole chat on every turn.

<details><summary>Mermaid source</summary>

```mermaid
---
config:
  layout: elk
---
flowchart LR
  subgraph TB1["TB1 · User's device"]
    E1["E1 Researcher"]
  end
  subgraph TB2["TB2 · Lab server"]
    P3("P3 Intake and indexing")
    P4("P4 Document search")
    P2("P2 Chat")
    P7("P7 Ollama, local model")
    DS1[("DS1 Database")]
    DS2[("DS2 Uploads folder")]
    DS3[("DS3 Vector store")]
  end
  E1 -->|"1 uploads a draft"| P3
  P3 -->|"2 original file · COPY 1"| DS2
  P3 -->|"3 full text · COPY 2"| DS1
  P3 <-->|"4 text pieces out, number codes back"| P7
  P3 -->|"5 pieces + codes + user id · COPY 3"| DS3
  E1 -->|"6 asks a question"| P2
  P2 -->|"7 question"| P4
  P4 <-->|"8 question out, code back"| P7
  DS3 -->|"9 closest pieces"| P4
  P4 -->|"10 passages"| P2
  P2 <-->|"11 whole chat + passages out, answer back"| P7
  P2 -->|"12 answer"| E1
  P2 <-->|"13 chat + passages saved · COPY 4"| DS1
  style TB1 fill:none,stroke:#d00,stroke-width:2px,stroke-dasharray:6 4
  style TB2 fill:none,stroke:#d00,stroke-width:2px,stroke-dasharray:6 4
```
</details>

## Figure 4 — Sharing a chat and the admin's reach

![Figure 4 — Sharing a chat and the admin's reach](figures/s2-share-admin.png)

Sharing makes a frozen copy that includes document passages but not the file (VERIFIED, run R08). The admin reads any record and downloads the whole database (VERIFIED, run R09), and by default nothing records it.

<details><summary>Mermaid source</summary>

```mermaid
---
config:
  layout: elk
---
flowchart LR
  subgraph TB1["TB1 · Users' devices"]
    E1["E1 Chat owner"]
    E2["E2 Colleague with grant"]
    E3["E3 Admin"]
  end
  subgraph TB2["TB2 · Lab server"]
    P5("P5 Share links")
    P6("P6 Admin functions")
    DS1[("DS1 Database")]
    DS2[("DS2 Uploads folder")]
  end
  N["Default log: no record of what the admin read"]:::note
  E1 -->|"1 shares a chat with a colleague"| P5
  P5 <-->|"2 frozen copy of the chat + access list"| DS1
  E2 -->|"3 opens the link, logs in"| P5
  P5 -->|"4 copy with document passages, not the file"| E2
  E3 -->|"5 asks for any chat, file, user list, statistics"| P6
  P6 -->|"6 everything, plus the whole database file"| E3
  P6 <-->|"7 reads any record"| DS1
  DS2 -->|"8 original files"| P6
  P6 -.- N
  linkStyle 5 stroke:#d00,stroke-width:3px
  classDef note fill:#fff7e0,stroke:#e08000,color:#333
  style TB1 fill:none,stroke:#d00,stroke-width:2px,stroke-dasharray:6 4
  style TB2 fill:none,stroke:#d00,stroke-width:2px,stroke-dasharray:6 4
```
</details>

## Figure 5 — What a deletion really removes (not a data-flow diagram)

![Figure 5 — What a deletion really removes (not a data-flow diagram)](figures/s3-deletion.png)

Green = removed, red = stays (both seen in runs R10–R12), amber = stays according to the code but not yet run. This is the picture to open the findings with.

<details><summary>Mermaid source</summary>

```mermaid
---
config:
  layout: elk
---
flowchart LR
  A1["User deletes a chat"]
  A2["User deletes a file"]
  A3["Admin deletes a user"]
  R1["Removed: chat, messages, share copy, tags"]:::gone
  S1["Stays: share access row; deleted text lingers in the database journal until it is tidied up"]:::stays
  U1["Stays if the answer was rated: full chat copy (code only, not yet run)"]:::unsure
  R2["Removed: file record, uploaded file"]:::gone
  S2["Stays: text pieces in the vector store"]:::stays
  S2b["Stays: passages already copied into chats"]:::stays
  R3["Removed: account, login, own chats"]:::gone
  S3["Stays: files (record, upload, full text), vector pieces, memories, notes, folders"]:::stays
  U3["Stays: rated chat copies (code only, not yet run)"]:::unsure
  A1 --> R1
  A1 -.-> S1
  A1 -.-> U1
  A2 --> R2
  A2 -.-> S2
  A2 -.-> S2b
  A3 --> R3
  A3 -.-> S3
  A3 -.-> U3
  classDef gone fill:#e6f4ea,stroke:#2e7d32,color:#222
  classDef stays fill:#fdecea,stroke:#c62828,color:#222
  classDef unsure fill:#fff7e0,stroke:#e08000,color:#222
```
</details>

## What was removed from the detailed diagram, and why it is safe

- P1 sign-in, P8 server-side outbound calls and the log store are merged into Figure 2. Their details stay in `architecture.md` and `data-flow-analysis.md` §5.1, §5.8, §5.9.
- Flow numbers `F1…F38` and asset IDs `A01…A10` are dropped from the pictures to keep them readable. The full level-1 diagram keeps them, so the report can cite either level.
- Nothing was deleted from the analysis itself: every flow of the detailed diagram is represented, sometimes merged with others, in at least one of Figures 2–4.
