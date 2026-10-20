# Local visual demo — DSC-59

Upload your files, describe what you want to solve, review the proposed task, then approve the work. Data acts as the data scientist: it determines appropriate treatment from the actual data and explains the best supported result, decisions, assumptions, sensitivities, and limitations in the app. Download the separate restocking list in the same format as your data; this CSV example produces a CSV file. A table-only HTML view of the same CSV opens in a separate tab for recording the demo.

Tracking: [DSC-59](https://linear.app/gr3enarr0w/issue/DSC-59), under the [DSC-9 MVP gate](https://linear.app/gr3enarr0w/issue/DSC-9).

The [product requirements](REQUIREMENTS.md) record the current user instructions and supersede contrary historical integration notes.

## Launch

From the application repository, with Python 3.11 or newer and `uv` installed:

```sh
uv sync --locked
uv run --no-sync streamlit run streamlit_app.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

Open `http://localhost:8501`. The server runs locally; there is no cloud service, database, account setup, separate frontend, or external REST endpoint. Native discovery needs the installed supported Codex CLI and network access to complete its plugin inventory. The reviewed deployment is macOS arm64, Codex 0.163.0 and Data 1.0.11 with the pinned skill identity. This does not establish portability to another host.

The current intake recognizes the selected retail CSV structure and preserves your original question and measured file identities. Approval authorizes Data to investigate the released development data. It must infer meaning from the contents and cross-file consistency, investigate null values and gaps in recorded dates, select evidence-supported methods and assumptions, and quantify their effects without follow-up questions. Existing Codex authentication stays outside the repository and is never included in UI output or receipts.

## Optional fixed engineering comparison

For a [DSC-60](https://linear.app/gr3enarr0w/issue/DSC-60) engineering run, the operator can set `SUIROAI_DEMO_COMPARISON_CONTRACT` to an absolute path to a trusted JSON **definition** file. The file contains the seven required nonempty text fields `target`, `baseline`, `primary_metric`, `population`, `dates`, `forecast_horizon`, and `selection_rule`; `secondary_diagnostics` is optional. Pass the definition directly, rather than a digest wrapper. See [task construction](dsc60-task-construction.md) for the approval and evaluation limits.

```sh
SUIROAI_DEMO_COMPARISON_CONTRACT=/absolute/path/to/comparison-contract.json PYTHONPATH=src .venv/bin/streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8504 --server.headless true --browser.gatherUsageStats false
```

Use an available fresh port to preserve existing sessions. The app reads at most 64 KiB and validates the file before creating a session. Relative paths, symlinks, missing or malformed files and incomplete definitions stop page actions; they never silently launch an uncontrolled comparison. Operator logs contain the configuration failure, while the page shows a brief configuration message. The file is reloaded on every rerun; changes or explicit removal of the environment setting revoke prior approval and results. An unchanged definition preserves the current result. Keep the file stable throughout a run.

With the environment variable unset, ordinary autonomous analysis is unchanged. This setting adds no customer configuration questions, automatic uploads, downloads, preview opening or analysis execution. Customers still review the readable proposal and explicitly approve each analysis.

## Try the actual supplied example

Add these four operational CSV files together in the single **Upload your data** area, from the explicitly selected `data/retail_mvp/sales_2022_2025/` directory. The backend identifies their meaning from actual column headers; filenames and selection order do not assign roles:

| Source | File |
| --- | --- |
| Sales | `supplied_sales/Sales_transactions_2022_2025.csv` |
| Inventory | `synthetic_inventory/inventory_position.csv` |
| Receipts | `synthetic_inventory/inbound_deliveries.csv` |
| Replenishment policy | `synthetic_ordering_rules/ordering_policy.csv` |

The app investigates what the uploaded data means. You do not need to label file roles or create extra documentation. Where the evidence cannot establish an answer, Data should return a useful, evidenced limitation and explain the assumptions and sensitivity of its best supported result.

Question: “What should I restock in my stores next week? I usually look at the last few months of sales to decide what to buy.”

Select **Review task**. The app automatically checks whether your question or uploaded contents already describe your current approach. When they do, it proceeds without asking you to confirm or repeat that description. When they do not, answer **How do you do this now?**, or select **Continue without a current approach**. An explicit statement that you have no current approach also permits review; policy files or ordering constraints alone do not establish your actual current process. Then inspect the proposed task and disclosed unknowns and select **Approve and run**. The context check does not perform the analytical investigation; that begins only after approval. The review uses readable sections for your goal, files, date, expected restocking list, data understanding, assumptions, and what approval allows. Proposal identifiers are retained internally and are not displayed in the app. No file is auto-loaded from the fixture directory. Split or unfamiliar CSVs are retained for Data to interpret; the selected historical demo needs a dated transaction source to isolate its reserved outcomes. Unreadable files produce specific guidance. A changed question, current-process answer, filename, or file byte revokes the old context decision, proposal and result. Stale context checks cannot populate a newer input revision. Repeated review of unchanged inputs reuses the context decision and is idempotent; a run permission is consumed once. Revise explicitly revokes consent even when input bytes are unchanged. Old results and exceptions cannot overwrite a newer proposal.

After approval, the page shows a neutral working indicator, then the actual analysis response or a specific execution problem. The response under **What we found** explains findings, restocking decisions, methods, assumptions, sensitivity, and evidence-based limits in plain language. **Download restocking list (CSV)** offers the separate data file with the restocking quantities. **View restocking list** opens the same CSV as a readable table in a separate browser tab. The CSV download and HTML view use their own exact stored outputs. The app response stays brief and uses everyday words, including why the method was chosen and an evidence-based estimate of running cost when usage and pricing support one. All customer explanation appears here in everyday words for a retail business owner. Detailed diagnostics stay internal. The HTML contains only the CSV headers, rows and exact values, with no narrative or extra summaries.

Records and approved source copies are retained in ignored `artifacts/demo/<session>/`; native receipts and controller audits have immutable references. These artifacts are local and must not be committed wholesale.

## Recorded-demo scenario presentation

The supplied stock, deliveries and ordering rules are assumed operating inputs within the user's requested demo roleplay. Fresh task reviews and Data explanations use that scenario directly, without asking for replacement data or adding synthetic/illustrative provenance flags to the new customer list. Actual source files and provenance remain unchanged in internal evidence; no independently verified real-stock claim or prior-run improvement is implied. This is presentation scope only, with no new customer setting and no change to models or evaluation. The rejected/deleted earlier recording must not be presented as the replacement take.

## Repeatable weekly calculation

Fresh Data runs prepare a reusable `restock_routine.py` with configurable input files, planning date and output, together with `routine_usage.md` and measured `routine_measurements.json` in the analytical workspace. The approved task review focuses on replacing recurring restocking hand calculations and identifying exceptions. The app continues to offer the explicit CSV download and separate HTML table; no schedule or automatic file action is installed. The usage artifact describes running the command again and how ChatGPT can help configure optional local scheduling. The recorded demonstration still uses November 30 development inputs, and local calculation time remains separate from AI-assisted analysis/build time and cost.

## Verification and reproduction

```sh
uv run --no-sync python -m pytest tests -q
```

For the actual browser attempt, install the optional browser tooling and its browser executable:

```sh
uv sync --locked --group browser
uv run --no-sync playwright install chromium
uv run --no-sync python scripts/check_demo_browser.py --data-root /absolute/path/to/data/retail_mvp/sales_2022_2025 --output /absolute/path/to/attempt-record
```

Start the app separately before running that command. The driver uploads the four actual operational files. It checks the proposal, clicks approval once, retains input hashes and screenshots, and records the actual outcome and available downloads. UI/component tests use explicit test doubles; the browser attempt records the real Data run, the plain-language response, and separate restocking and HTML outputs.

A network-restricted terminal may cause Codex plugin inventory to return its remote-marketplace fallback warning. The existing policy rejects that incomplete inventory. The normal network-enabled host inventory was checked successfully; no fallback or guard relaxation was added. Native permission, browser-launch, and localhost-bind errors from a restricted executor must be distinguished from app failures.


Current-process context is part of the approved task, whether detected from supplied material, entered in response to the missing-context question, or explicitly omitted with **Continue without a current approach**. There is no preliminary selector asking where you shared it. Edits revoke approval and prior outputs. Data still resolves cleaning and analytical choices autonomously, and comparisons must not invent an incumbent method when none was supplied. The same-window response assesses the selected non-LLM model's local-computer suitability and routine costs separately from AI-assisted analysis/build costs.

CSV downloads start only when the user clicks the download button. The recording/browser checker leaves the explanation in the main window, without opening or downloading files by default. Add `--open-preview` only to explicitly check the HTML in a separate tab, and `--download-csv` only to explicitly check file saving. Main-window or preview-only success does not claim CSV transport was verified or the full milestone accepted.

## Internal call tracing and engineering comparison

Each detector/analysis attempt now has a sibling `native-trace/` directory containing `outbound-prompt.txt` and `call-trace.json`. The prompt is saved before dispatch; the receipt links exact input hashes, requested/exposed settings, thread/turn IDs and native logs. The original question stays separate from derived context. These files are internal, with no new user action. Trace visibility excludes hidden provider/system context.

`DemoSession(comparison_contract=definition)` optionally binds an explicitly supplied engineering comparison to the reviewed task. It does not infer or invent business rules. Normal app sessions leave it unset so Data owns analytical choices. For controlled engineering validation, `scripts/dsc60_workflow_replay.py` traverses the real service review/approval/backend path with a fixed supplied contract and retained detector context; it is not a user-operated browser recording. `scripts/dsc60_trace_replay.py` separately replays retained exposed prompts unchanged. Both use the existing restricted native host, preserve December outcomes and allow healthy analysis to finish. [DSC-60 evidence](../../evidence/demo/dsc60-debug-2026-10-20/README.md) distinguishes those runs from the pair with shared controls and from final performance acceptance.

Completed analyses now pass through a separate native business-writing turn before the final explanation is published. It receives bounded findings, aggregate comparison/workload evidence, original model rationale and CSV identity/counts; it cannot change the CSV, HTML or fitted model. This is an additional AI-assisted presentation call, separate from the non-LLM routine calculation. Exact prompts and lineage are retained internally. Current approval is checked before dispatch and publication; a failed writing step keeps the useful original findings. See [the final DSC-60 evaluation and writing evidence](../../evidence/demo/dsc60-debug-2026-10-20/final-evaluation/README.md).

The final explanation now focuses on the automated weekly task. The native adapter retains only allowlisted numeric model-usage counters alongside existing traces. Trusted detector usage is bound to the approved proposal, and the final controller estimates intake+analysis+writing cost after all three complete. The appended standard-API-rate estimate has its own published immutable response reference; original writer bytes and actual Codex billing remain separate. Known long-context requests produce a pricing range. Scheduling language must be supported by the generated configurable routine and usage guide; the app installs no schedule.
