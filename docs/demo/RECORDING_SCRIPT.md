# Reproducible recording script — preparation only

Follow the [gate](README.md) and [checklist](CHECKLIST.md) first. This is an
operator script for the eventual integrated supported environment, not an
executable analytical launcher. There is currently no documented supported
end-to-end retail command. Do not invent one or replay prewritten outcomes.

## Before the recording

1. Pin the tested integration commit from `nightly`; use that exact commit for
   capture and reproduction. Use a clean checkout, or retain and hash every
   tracked diff and relevant untracked code/config file needed to reproduce it.
   Retain OS/architecture, Python/lock/environment,
   Codex/Data/model identity and skill hash, native profile/effective inventory,
   and required credential **names/setup only**, never secret values. Confirm
   the actual supported host with DSC-26; upgrades require revalidation.
2. Have DSC-10/26 supply the actual invocation procedure, working directory,
   input mapping, output retrieval and finite limits. Save its exact command or
   native control request sequence as a replay recipe, plus code/config bytes.
   `StageAdapter.execute(stage_request_ref, handoff_refs=..., external_refs=...)`
   is the existing boundary, not a complete command or a new Data API. No mocks,
   echo reviewers, manufactured approvals or Code Interpreter substitution.
3. Preserve the actual request and supplied file identities. The intended local
   root is `/Users/ceverson/Development/SuiroAI/data/retail_mvp/sales_2022_2025/`.
   Record the five inputs and two provenance documents below. Measure hashes
   before and after; stop on unexplained changes. These commands only inspect
   bytes and versions and must run in the trusted capture/controller context,
   outside the restricted feature/model-selection context. Run this first block
   from the application Git root `/Users/ceverson/Development/SuiroAI/suiroai/`
   or the recorded equivalent application worktree, not the workspace parent:

   ```sh
   git rev-parse HEAD
   git status --short
   python3 --version
   shasum -a 256 pyproject.toml uv.lock docs/contracts/SNAPSHOT.json
   shasum -a 256 src/suiroai/contracts/schema/retail-contract.schema.json
   ```

   From the data root:

   ```sh
   shasum -a 256 supplied_sales/Sales_transactions_2022_2025.csv supplied_sales/sales_data_dictionary.csv synthetic_inventory/inventory_position.csv synthetic_inventory/inbound_deliveries.csv synthetic_ordering_rules/ordering_policy.csv documentation/synthetic_generation_manifest.json documentation/shared_locations.json
   ```

4. Reconcile measured source hashes with the generation manifest, preserve Drive
   IDs from `shared_locations.json`, and retain the generator reference/seed
   `20261016`. Manifest QA is source evidence only. Supplied history has unverified
   origin/license/completeness; operational values are explicit synthetic inputs,
   not inferred real stock or supplier facts. Held-out outcomes are evaluation
   evidence, never November 30 decision inputs.
5. Allocate a restricted capture bundle. Copy the
   [blank index](../../evidence/demo/index.template.csv)
   outside the source tree. Leave absent evidence unrecorded. Start continuous
   screen capture on the existing interaction surface with UTC start time;
   record pauses and edits. Keep the original recording and internal event log.

## Capture this one task

| Segment | Operator action and visible proof | Evidence retained internally |
| --- | --- | --- |
| A — request and files | Show the actual user request and actual supplied files/accessibility. A possible request, **only a suggestion until the user submits it**, is: “Using these files, produce an illustrative product/store restocking list as of November 30, 2025, with findings and limitations.” Receiving files does no joining/preparation. | Original request bytes/event, submission and input versions, file refs/hashes. |
| B — proposed task | Show the parent's step-2 proposed goal, same-case inputs, historical context, synthetic assumptions and material gaps with reasons. If a genuine gap occurs, capture guidance and correction within this task; do not remove a file merely to manufacture a second demo. | Exact proposal/version/digest and submission-bound guidance. Missing files are not silently replaced by fixtures. |
| C — sign-off | Capture the actual user's explicit approval of that proposal/input version. Silence waits. Rejection, correction or new material data returns to B and invalidates old consent. | Authenticated approval and current binding; no separate post-sign-off task definition. |
| D — bounded execution | Show that the parent released this approved task to real Codex with OpenAI Data and retrieved real artifacts. Use a reviewer view of actual invocation IDs/receipts; do not display routine EDA/model progress as customer narration. | Current execution contract, limits, exact stage requests/permissions, native thread/turn/command IDs, Data skill binding, actual code/config/logs, outputs and parent adoption receipts. |
| E — preparation to freeze | Inspect the evidence in the order below. Show actual checkpoint decisions and immutable references, not prepared score slides. | Preparation/lineage → EDA findings/artifacts → initial-feature definitions/checks → initial baseline/model scores → LLM additional definitions → materialization/checks → bounded comparison → frozen model/features/preprocessing and separate November 30 forecast. |
| F — reserved validation | Show the frozen choice and predeclared gate before authorized December access, then actual scores, coverage and parent decision. Follow the honest failure branch below if necessary. | Frozen plan/rule/population, release timing, fully observed target horizons, measured scores and bounded review/recheck evidence. |
| G — verified delivery | Only after validation passes: show independent arithmetic check, actual parent numerical approval, final draft verification, parent permission and actual delivered report. | Candidate v1 → independent evidence → approved v2 with unchanged candidate values → report → independent check → delivery permission/readback. |

After C, the parent creates the approved execution contract/run namespace and
authorizes bounded stage releases; the recorder never manufactures that authority.
For E, development uses 2022–2024 and rolling validation through November 30,
2025; every development target horizon ends by that cutoff. The feature-generation
and selection contexts receive only permitted development artifacts. Retain the
actual context allowlist/content hashes and supported isolation controls: a date
instruction alone is insufficient. Do not attach unrestricted raw sales, full QA
profiles, partition audits or December summaries. Fit transforms within training
folds. Keep initial baseline review before the required LLM feature generation,
and materialize/validate those definitions before comparing the shortlist.
Baseline/candidates use common records, origins, horizons and metrics. Better
proceeds with parent review; equal/worse follows its bounded internal review.

For F, freeze model/config, features, preprocessing, fit lineage, forecast,
metric/direction, threshold/tolerance and minimum coverage before holdout release.
Retain the `dsc28-frozen-v1` bundle, detached manifest and exact plan/rule bytes.
Score fully observed December horizons only. Never fit, select, tune or adjust
November 30 quantities from December outcomes. A demonstrable scoring/runtime
defect may receive a prior authorized bounded recheck with frozen bindings
unchanged; no runner-up, threshold change or indefinite review.

For G, verify lead time plus review horizon, safety stock, usable stock, timely
receipts, zero clamp and positive-order minimums/multiples. Never subtract both
the on-order summary and receipt lines or let late receipts cure earlier shortage.
Preserve exceptions and reliably bound product names. The one final report must
contain the illustrative Product_ID/Product_Name/Store_ID/OrderQty/Quantity_Unit
list, concise verified EDA/feature findings, measured results and limitations.
It must disclose synthetic operations and avoid unsupported profit/stockout claims.
No new final customer sign-off is required.

## If execution fails

Retain the real failure, any partial outputs and the exact failed stage. Capture
parent review and the independently verified terminal explanation when available.
It must say this MVP could not produce a reliable solution with the supplied
data/scope and give the evidenced reason. Absent scores do not prove measured
underperformance: classify from actual typed stage/parent evidence, preserving
missing-input/material-fact guidance separately from execution failure. Do not present an order list as
valid, stage a successful ending, or claim the business problem is impossible.
If verification/delivery is blocked, retain that blocker rather than call the
explanation verified or delivered. A failure-only recording evidences its actual
handling and explicitly lists missing success evidence; it does not complete
the successful restocking demonstration.

## Seal and reproduce

Stop capture after actual delivery or terminal blocker. Retain original recording
bytes, duration, SHA-256, storage/reference and UTC times. Map every segment to
native/event timestamps and exact artifact refs in the index; preserve edit/pause
history and link any shorter edit to its original. Remeasure source/output bytes,
record expected versus actual results and obtain named independent decisions.
Compare the delivered UTF-8 bytes with the exact approved draft/readback.

A second operator must be able to obtain the retained authorized inputs and
environment pins and follow the saved invocation recipe without fixture injection.
Reproduction uses a fresh run/output namespace and new genuine approval when
required; it must not overwrite evidence or describe an already exposed December
holdout as unseen for changed selection. Retain nondeterministic LLM provenance
and tolerances; do not promise identical generated prose or invent measured scores.
Return the actual recording and completed index only after genuine execution.
