# Local visual demo — DSC-59

This is an **incomplete integration build**, not a completed end-to-end restocking demo. It provides the real browser input/review/approval loop and runs genuine native discovery. A controller-only audit separates the supplied development transactions from December and measures coverage without inventing zeros or historical availability. Analytical stages and verified report delivery remain blocked. The download is deliberately unavailable.

Tracking: [DSC-59](https://linear.app/gr3enarr0w/issue/DSC-59), under the [DSC-9 MVP gate](https://linear.app/gr3enarr0w/issue/DSC-9).

## Launch

From the application repository, with Python 3.11 or newer and `uv` installed:

```sh
uv sync --locked
uv run --no-sync streamlit run streamlit_app.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

Open `http://localhost:8501`. The server runs locally; there is no cloud service, database, account setup, separate frontend, or external REST endpoint. Native discovery needs the installed supported Codex CLI and network access to complete its plugin inventory. The reviewed deployment is macOS arm64, Codex 0.163.0 and Data 1.0.11 with the pinned skill identity. This does not establish portability to another host.

The current intake is deterministic and restricted to the selected retail schema; it preserves the typed original question and measured file identities. No live understanding/humanizer model or full analytical model run is claimed. The present discovery/audit attempt requires no API key environment variable. A configured real analytical provider and trusted independent numerical/semantic review are still needed before full execution. Existing Codex authentication stays outside the repository and is never included in UI output or receipts.

## Try the actual supplied example

Upload these five separate CSV files from the explicitly selected `data/retail_mvp/sales_2022_2025/` directory:

| Control | File |
| --- | --- |
| Sales | `supplied_sales/Sales_transactions_2022_2025.csv` |
| Data dictionary | `supplied_sales/sales_data_dictionary.csv` |
| Inventory | `synthetic_inventory/inventory_position.csv` |
| Receipts | `synthetic_inventory/inbound_deliveries.csv` |
| Replenishment policy | `synthetic_ordering_rules/ordering_policy.csv` |

Question: “Using these files, produce an illustrative product/store restocking list as of November 30, 2025, with findings and limitations.”

Select **Review task**, inspect the proposed task and disclosed unknowns, then **Approve and run**. No file is auto-loaded from the fixture directory. An absent or incompatible file produces specific guidance. A changed question, filename, role, or file byte revokes the old proposal/result. Repeated review is idempotent; a run permission is consumed once. Revise explicitly revokes consent even when input bytes are unchanged. Old results and exceptions cannot overwrite a newer proposal.

Current expected result: **blocked before model execution**, with no recommendation file. This is correct blocker handling, not completion of the successful example. Records and approved source copies are retained in ignored `artifacts/demo/<session>/`; each native discovery receipt and controller audit has an immutable reference. These artifacts are local and must not be committed wholesale.

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

Start the app separately before running that command. The driver uploads the actual selected files, checks the proposal, clicks approval once, retains input hashes and screenshots, and records whether a verified download is available. It currently exits **2** for the honest blocked result. It cannot establish acceptance from a download alone; independent delivery/readback still has to be connected. UI/component tests use explicit test doubles and are not real analytical evidence.

A network-restricted terminal may cause Codex plugin inventory to return its remote-marketplace fallback warning. The existing policy rejects that incomplete inventory. The normal network-enabled host inventory was checked successfully; no fallback or guard relaxation was added. Native permission, browser-launch, and localhost-bind errors from a restricted executor must be distinguished from app failures.
