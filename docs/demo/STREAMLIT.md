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

## Try the actual supplied example

Add these four operational CSV files together in the single **Upload your data** area, from the explicitly selected `data/retail_mvp/sales_2022_2025/` directory. The backend identifies their meaning from actual column headers; filenames and selection order do not assign roles:

| Source | File |
| --- | --- |
| Sales | `supplied_sales/Sales_transactions_2022_2025.csv` |
| Inventory | `synthetic_inventory/inventory_position.csv` |
| Receipts | `synthetic_inventory/inbound_deliveries.csv` |
| Replenishment policy | `synthetic_ordering_rules/ordering_policy.csv` |

The app investigates what the uploaded data means. You do not need to label file roles or create extra documentation. Where the evidence cannot establish an answer, Data should return a useful, evidenced limitation and explain the assumptions and sensitivity of its best supported result.

Question: “Using these files, produce an illustrative product/store restocking list as of November 30, 2025, with findings and limitations.”

Select **Review task**. The app automatically checks whether your question or uploaded contents already describe your current approach. When they do, it proceeds without asking you to confirm or repeat that description. When they do not, answer **How do you do this now?**, or select **Continue without a current approach**. An explicit statement that you have no current approach also permits review; policy files or ordering constraints alone do not establish your actual current process. Then inspect the proposed task and disclosed unknowns and select **Approve and run**. The context check does not perform the analytical investigation; that begins only after approval. The review uses readable sections for your goal, files, date, expected restocking list, data understanding, assumptions, and what approval allows. Proposal identifiers are retained internally and are not displayed in the app. No file is auto-loaded from the fixture directory. Split or unfamiliar CSVs are retained for Data to interpret; the selected historical demo needs a dated transaction source to isolate its reserved outcomes. Unreadable files produce specific guidance. A changed question, current-process answer, filename, or file byte revokes the old context decision, proposal and result. Stale context checks cannot populate a newer input revision. Repeated review of unchanged inputs reuses the context decision and is idempotent; a run permission is consumed once. Revise explicitly revokes consent even when input bytes are unchanged. Old results and exceptions cannot overwrite a newer proposal.

After approval, the page shows a neutral working indicator, then the actual analysis response or a specific execution problem. The response under **What we found** explains findings, restocking decisions, methods, assumptions, sensitivity, and evidence-based limits in plain language. **Download restocking list (CSV)** offers the separate data file with the restocking quantities. **View restocking list** opens the same CSV as a readable table in a separate browser tab. The CSV download and HTML view use their own exact stored outputs. The app response stays brief and uses everyday words, including why the method was chosen and an evidence-based estimate of running cost when usage and pricing support one. All customer explanation appears here in everyday words for a retail business owner. Detailed diagnostics stay internal. The HTML contains only the CSV headers, rows and exact values, with no narrative or extra summaries.

Records and approved source copies are retained in ignored `artifacts/demo/<session>/`; native receipts and controller audits have immutable references. These artifacts are local and must not be committed wholesale.

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
