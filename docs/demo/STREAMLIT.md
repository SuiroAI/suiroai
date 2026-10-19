# Local visual demo — DSC-59

Upload your files, describe what you want to solve, review the proposed task, then approve the work. Data determines appropriate treatment from the actual data and returns the best supported result with assumptions, sensitivities, and limitations. The page distinguishes generated analysis output, execution problems, and independently verified final delivery. A generated file can be useful before independent verification; its label states that limitation.

Tracking: [DSC-59](https://linear.app/gr3enarr0w/issue/DSC-59), under the [DSC-9 MVP gate](https://linear.app/gr3enarr0w/issue/DSC-9).

The [product requirements](REQUIREMENTS.md) record the current user instructions and supersede contrary historical integration notes.

## Launch

From the application repository, with Python 3.11 or newer and `uv` installed:

```sh
uv sync --locked
uv run --no-sync streamlit run streamlit_app.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

Open `http://localhost:8501`. The server runs locally; there is no cloud service, database, account setup, separate frontend, or external REST endpoint. Native discovery needs the installed supported Codex CLI and network access to complete its plugin inventory. The reviewed deployment is macOS arm64, Codex 0.163.0 and Data 1.0.11 with the pinned skill identity. This does not establish portability to another host.

The current intake recognizes the selected retail CSV structure and preserves your original question and measured file identities. Approval authorizes Data to investigate the released development data. It must infer meaning from the contents and cross-file consistency, investigate null values and gaps in recorded dates, select evidence-supported methods and assumptions, and quantify their effects without follow-up questions. Existing Codex authentication stays outside the repository and is never included in UI output or receipts. Full numerical verification and final delivery remain separate acceptance requirements.

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

Select **Review task**, inspect the proposed task and disclosed unknowns, then **Approve and run**. The review uses readable sections for your goal, files, date, expected report, data understanding, assumptions, and what approval allows. Its technical identifier is collapsed under **Technical details**. No file is auto-loaded from the fixture directory. Split or unfamiliar CSVs are retained for Data to interpret; the selected historical demo needs a dated transaction source to isolate its reserved outcomes. Unreadable files produce specific guidance. A changed question, filename, or file byte revokes the old proposal/result. Repeated review is idempotent; a run permission is consumed once. Revise explicitly revokes consent even when input bytes are unchanged. Old results and exceptions cannot overwrite a newer proposal.

After approval, the page shows a neutral working indicator, then the actual analysis response or a specific execution problem. Findings appear under **What we found**. If Data produces an HTML output, **Download Data output** offers its exact stored bytes, labelled **Data-generated development report; not independently verified.** This is distinct from an independently verified final report.

Records and approved source copies are retained in ignored `artifacts/demo/<session>/`; native receipts and controller audits have immutable references. These artifacts are local and must not be committed wholesale. DSC-59 remains open until the actual supplied example completes the full independently verified delivery path.

## Remaining work before successful acceptance

1. Publish and adopt a reviewed contract revision for controller-measured partition lineage and safe derived-development release, including derived feature summaries. Keep December source bytes inaccessible to model/feature selection.
2. Resolve the actual target, missing-date, and historical information-availability policy with truthful evidence or explicit scenario assumptions. Approval of this UI proposal does not silently authorize unknown dates as zeros or invent old knowledge timestamps.
3. Allow a pending execution acceptance policy during initial development, then bind a justified immutable concrete final rule before freeze and holdout access. Do not insert an arbitrary number merely to satisfy the old schema.
4. Connect real preparation, initial evaluation, additional LLM features, bounded comparison/freeze and untouched validation through the parent/adapter. Native discovery is not analytical execution.
5. Connect independent numerical approval before humanization, native check-only verification transport, evidence-based claim review, and exact final HTML delivery/readback. The report finding-ID collision has been fixed and its positive and forged-duplicate regressions retained.
6. Rerun the real example through the browser, compare the downloaded bytes with the independently verified final artifact, retain the successful recording, and complete DSC-31/56/9 review. Until then DSC-59 remains open.

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

Start the app separately before running that command. The driver uploads the four actual operational files. It checks the proposal, clicks approval once, retains input hashes and screenshots, and records the actual outcome and available downloads. A generated output does not by itself establish independently verified final delivery. UI/component tests use explicit test doubles and are not real analytical evidence.

A network-restricted terminal may cause Codex plugin inventory to return its remote-marketplace fallback warning. The existing policy rejects that incomplete inventory. The normal network-enabled host inventory was checked successfully; no fallback or guard relaxation was added. Native permission, browser-launch, and localhost-bind errors from a restricted executor must be distinguished from app failures.
