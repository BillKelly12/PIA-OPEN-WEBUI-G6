# pia/ — PIA working files (Group 6)

(Folder named `pia/` because the upstream Open WebUI repo already has its own `docs/`.)

All text here was drafted with an AI assistant and **must be vetted by the team before it is used in the report**. Nothing below is final. Last updated: 29 Oct 2026.

## What is where, and its status

| File | What it is | Status |
|---|---|---|
| `architecture-simple.md` + `figures/` | Five small diagrams (stakeholders, context, upload and ask, share and admin, deletion map) | Baseline: local-only use case. To be pruned so that every element appears in the findings, and the other way round (teacher's rule of 28 Oct). |
| `architecture.md`, `architecture-dfd.svg`, `architecture-components.svg` | Detailed level-1 DFD with flow and asset IDs, component evidence | Baseline, local-only. Kept as the detailed appendix. |
| `data-flow-analysis.md` | Data inventory, flows, trust boundaries, volumes, open questions; every claim tagged VERIFIED or HYPOTHESIS | Baseline, local-only. Valid whatever the team decides. §5.8 (what leaves) is where the extended use case would grow. |
| `draft1-review.md` | Review of the 1st draft | Written **before** the teacher's input of 28 Oct. Its §5 (findings options) is superseded by `option-b-plan.md`; the rest still holds. |
| `option-b-plan.md` | Proposal: extend the use case with an external model; issues B1–B8, techniques from the course, tests | **Proposal, not a decision.** To be agreed by the team (and, ideally, the TAs). |
| `verification/` | Scripts that reproduce every "VERIFIED (run R##)" claim; last output | Baseline. Needs extending with an OpenAI-protocol stub for Option B. |
| `tests/` | **Eight privacy tests** on the official Open WebUI test harness: `bash pia/tests/run.sh`; see `tests/README.md`. All fail today by design. | New (29 Oct). To be vetted by the code pair. |
| `diagrams/` | Mermaid sources of all figures | — |

## Vetting checklist (suggested split)

| Who | Check | How |
|---|---|---|
| Code pair | Reproduce the runs | Follow `verification/README.md`; compare with `verification/last_run_output.txt`. Report any line that says DIFFERS. |
| Code pair | Spot-check 10 code references each | Open the `file:line` cited in `data-flow-analysis.md` §3 and §5.7 at commit `6a18585` and confirm the claim. |
| Code pair | Turn the HYPOTHESIS items B1–B3 into VERIFIED or drop them | Stub provider test in `option-b-plan.md` §3. |
| Report pair | Check GDPR article mappings | Against the legal lecture slides (30 Sept) and the guidelines. The articles in `draft1-review.md` and `option-b-plan.md` are candidates. |
| Report pair | Check external facts and quotes | The OpenAI quotation in the 1st-draft intro; the Giskard and Presidio notes in `option-b-plan.md`. |
| Everyone | Read in this order | `architecture-simple.md` → `option-b-plan.md` → `draft1-review.md` §3 → the rest as reference. |

Unverified statements are marked HYPOTHESIS in the files; if you cannot confirm a VERIFIED claim, change its tag.

## Figure formats
Each figure exists as **PNG** (use in slides and Word), **PDF** (vector, text embedded; use in LaTeX with `\includegraphics`) and **SVG** (editable source, labels stored as plain text). If an SVG shows empty boxes in a viewer, use the PNG or PDF. Regenerate from `diagrams/*.mmd` with `mmdc` (see `verification/README.md`).
