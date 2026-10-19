# DSC-59 final CSV + HTML demo evidence

Tracking: https://linear.app/gr3enarr0w/issue/DSC-59

Source revision: `5b0eee4` on `codex/dsc-59-streamlit-demo`. Full suite: **726 passed and 659 subtests passed**.

The actual four supplied CSV files were uploaded in the visible Streamlit app. The November 30 question was reviewed and approved once. Genuine GPT-6.1-Sol medium Data completed autonomously with no overall deadline, producing a plain-language app response, standalone restocking CSV and separate HTML demo report. The final screenshot shows both download controls and the response. The files contain 336 product/store recommendations, totaling 888 units across 113 positive-order pairs.

`restocking.csv`, `report.html`, `response.md` and `result.json` are exact copies of final local run output. Both file digests match the immutable application artifact references. They are **not browser-downloaded evidence**: both controls were clicked and native Save dialogs completed, but no files persisted. Brave displayed **Blocked by your organization** for the CSV. No security policy was bypassed or changed. Final browser-save acceptance and opening the downloaded HTML therefore remain outstanding.

`check_final_run.py` independently recomputes all 336 recommendations, five sensitivities and six candidate methods across 66 folds using the released local inputs. It checks every recommendation-table cell against the HTML. Run locally with `python3 evidence/demo/dsc59-final-outputs-2026-10-19/check_final_run.py` while ignored run artifacts are available. Its final audit passed with zero mismatches. Raw sources and native transcripts are intentionally not committed.

Historical evidence in the earlier data-handoff folder remains unchanged. This folder supersedes its output wording and single-output behavior. Separate nightly review, recording and milestone acceptance remain open in Linear.
