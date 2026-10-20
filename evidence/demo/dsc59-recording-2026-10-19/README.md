# Three demo examples — October 19, 2026

Issue: [DSC-59](https://linear.app/gr3enarr0w/issue/DSC-59).
Application source: `b243957ed381528908f7594cd8e5d1b7b98203ba`.

The user operated the screen recorder while the agent controlled the real local
Streamlit app at port 8503. The same four uploaded retail CSVs were used, without
a data dictionary. The user expressly authorized these files to be sent to the
existing OpenAI Codex/Data model for all three examples. Each analysis required
one separate approval in the app. These are actual executions, not prerecorded
results injected into the interface.

| Editing order | Take | Demonstrated context flow |
| --- | --- | --- |
| 1 | `case1-retake-*` | Current method supplied naturally in the question; detected without another question. |
| 2 | `case2-*` | Current method missing; app asks how the user does it now, then accepts a short answer. |
| 3 | `case3-*` | Current method missing; user explicitly continues without an existing approach. |

The actual capture order was original case1, case2, case3, then case1 retake.
**Use the retake for example one.** The original case1 analysis passed its
arithmetic check, but its visual take did not explicitly scroll through the full
response. It is retained as historical evidence and superseded for editing.

For case2, case3 and case1 retake, the agent explicitly scrolled through the
complete app explanation, including the final running-cost paragraph. The agent
then manually opened the HTML results in a new tab, showed and scrolled its
table, and returned to the app. CSV download was never clicked during these
takes; neither file action started automatically. HTML contains only the CSV
table. The independent reviewer checked every live HTML table cell and row
against its delivered CSV, as well as source-based ordering arithmetic.

`recording-index.json` binds the questions, context decisions, exact run IDs,
receipts, output hashes and UI observations. The CSV and HTML files here are exact
copies of generated artifacts, not claimed browser downloads. Receipt summaries
omit native command transcripts and source samples. The Python audit companions
recompute quantities independently; they do not execute generated analysis code.

The original user-operated video has not been supplied. Its path, hash, duration,
continuity, framing and eventual edit have not been independently verified.
Screenshots document the observed UI but are not a substitute for that video.
Loading periods remain in the user's capture for editing. These exploratory demo
runs do not close the separate frozen December holdout, authenticated
verification/delivery, browser-download-policy or final milestone acceptance
requirements. Routine calculation cost/local-computer statements are separate
from the unmetered AI-assisted analysis/build cost.
