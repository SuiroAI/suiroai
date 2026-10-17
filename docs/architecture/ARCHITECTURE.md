# Single retail restocking MVP architecture — DSC-3

Decision revision 0.1.0 · October 17, 2026 · M01 only.

## Decision and implementation status

Use the existing `suiroai/` application area as one independently packaged Python application, with `suiroai/pyproject.toml` and `suiroai/src/suiroai/`. Keep the existing `dscraft/` library and repository separate and unchanged. Reserve one module area per component in [OWNERSHIP.md](OWNERSHIP.md). This is a development ownership map, not a collection of autonomous runtime agents.

Workspace inspection found an empty `suiroai/`, no workspace-root Git repository, and a separate clean DSCraft repository. Existing `docs/MVP_ROLE_BASED_PROMPTS.md` describes future assignments, not working components. The inspected DSCraft checkout is `ed568686b1c5bfe16a058f6b64c8f898b5d41b76`, package version `0.2.1`, Python `>=3.11`.

The application foundation is limited to package metadata/root initialization and local development instructions. Actual DSC-24/26 owners have now acknowledged the layout and exclusive paths; DSC-3 added only that foundation and the `jsonschema>=4.18,<5` dependency requested by DSC-24. No server, CLI/customer executable, dashboard, generic task router, plugin runtime, phase-agent framework or DeepAgents integration is required. Further dependencies are added through DSC-3 only after the owning component identifies a demonstrated need. LangChain is for focused understanding/feature-definition/humanizing calls. DSC-10 may use LangGraph for explicit state, branching, approval wait and resume; it does not delegate transition authority to analytical stages.

This document defines the implementation boundary. It does not establish a concrete schema snapshot or demonstrate supported execution. Actual layout/path acknowledgments are recorded in [COORDINATION.md](COORDINATION.md); the DSC-24 draft snapshot and DSC-26 real execution-boundary evidence still require review. The broader DSC-3/V1 architecture remains open.

## Sources and limits of inspection

Read through the connected Linear tools: [DSC-3](https://linear.app/gr3enarr0w/issue/DSC-3), [DSC-24](https://linear.app/gr3enarr0w/issue/DSC-24), [DSC-26](https://linear.app/gr3enarr0w/issue/DSC-26), and the [single-case contract](https://linear.app/gr3enarr0w/document/retail-mvp-single-restocking-case-shared-data-and-implementation-72e8278521db). Read-only subagent review also inspected DSC-10, DSC-25, DSC-27–31, DSC-56 and DSC-9. These issues were Backlog implementation plans at inspection; their descriptions are requirements, not execution evidence. Core issue comments did not supply an implementation agreement or completed invocation evidence.

Local sources inspected include the active data README, dictionary, provenance manifests, existing role prompts, and DSCraft exports/source/tests. Tests were inspected, not executed for library certification. Drive file IDs are recorded in the local manifest; this assignment did not independently fetch Drive content. Miro was not modified or used as evidence of implemented behavior. No external API support is inferred from a product name or installed skill.

## Component boundary and exact customer workflow

The parent is the only component that advances the workflow or authorizes a checkpoint. The analytical work is one approved bounded task in the supported Codex/Data environment; module boundaries describe callable responsibilities and artifacts, not separate autonomous services.

| Customer step | Responsible implementation | Inputs, output and parent checkpoint |
| --- | --- | --- |
| 1. Supply request/data | DSC-25 `intake/` | Capture original request, actual supplied references, accessible/missing status and immutable input version. Receipt performs no joining or analytical preparation. Demo files are not automatically customer-supplied files. |
| 2. Propose task and explain gaps | DSC-25 with DSC-10 | Read-only inspection forms proposed goal/output, input references, material facts/assumptions and missing data with reasons. Parent exposes the proposal. No cleaning, target construction or model work. |
| 3. Customer sign-off | DSC-10, conversation via DSC-25 | Bind approval to exact proposal and input versions. Rejection/correction/material new data returns to step 2; silence remains waiting. Execution uses that same approved task without a second task-definition stage. |
| 4. Approved preparation | DSC-26 transport; DSC-27 analysis | Parent checks approval, allowed actions, source versions and budget. Codex/Data cleans and joins only now. Adapter returns actual execution artifacts/errors, not self-asserted completion. |
| 5. EDA and initial features | DSC-27 `preparation/` | Return development-only data/features, lineage, join/quality/timing checks and concise verified findings. Routine EDA remains internal. |
| 6. Initial model versus baseline | DSC-28 `modeling/` | Use one common development evaluation plan. Return measured better/worse/equal and coverage evidence; parent owns proceed/review/stop decisions. Better supports step 7; equal or worse requires bounded evidence review under the approved contract, never silent bypass. |
| 7. LLM-generated additional features | DSC-28 | LLM proposes definitions, source/timing/rationale; Codex/Data materializes and validates them with training-only fitting and prediction-time availability. No raw future rows/full-history summaries in the feature-generation context. |
| 8. Bounded shortlist and freeze | DSC-28 | Compare the prebounded candidates on the common development plan; freeze model, feature definitions, preprocessing, code/config, fit-data lineage, acceptance rule and evaluation eligibility. Save the November 30 forecast as a separate immutable artifact. Parent checks evidence and authorizes final evaluation. |
| 9. Unseen evaluation | DSC-28; DSC-10 review | Evaluate the frozen choice on reserved December outcomes, fully observed horizons only. Pass permits step 10. Failure enters the finite internal review described below. Never choose the runner-up, tune on holdout or keep reviewing indefinitely. |
| 10. Restocking calculation and verification | DSC-29 `replenishment/`, DSC-30 `verification/`, DSC-10 | Calculate from frozen November 30 forecasts and as-of operational inputs only after validation passes. Independently check quantities, receipt timing and exceptions; parent approves verified quantities for the report. |
| 11. One verified final response | DSC-29 `reporting/`, DSC-30, DSC-10 | Success report contains approved item/quantity list, concise verified analytical/feature findings, measured results and material limitations. Failure response contains the verified scoped explanation without a purportedly valid list. Parent authorizes delivery; no separate technical-report deliverable. |

Customer interactions are limited to the initial proposal/sign-off, irreducible material business-fact gaps, genuine blockers and final delivery. Customers do not choose algorithms, imputation or hyperparameters. No routine analytical progress is streamed. Internal findings and evidence remain available for the final response.

### Failure and recovery boundary

Four meanings must remain distinct in the DSC-24 contracts: missing-data guidance, measured validation failure, execution failure and successful recommendations. Capability unavailable/unsupported integration is a genuine blocker, not a measured model result. Worker-reported status is evidence for the parent, not permission to deliver.

On final validation failure, DSC-10 reviews DSC-28's scores, coverage, frozen bindings and logs. Confirmed underperformance leads directly to a failure draft. Only a demonstrable implementation, calculation or runtime defect may justify correction, within a predeclared finite attempt/time budget. The model choice, feature set, preprocessing policy, acceptance rule, permitted fit data and saved November 30 forecast values/inputs/fit remain unchanged after December access. Bounded correction may fix scoring, runtime or verification defects against those unchanged frozen artifacts and must record the exact defect, affected evidence and recheck; it cannot become re-selection or holdout fitting. If the freeze was compromised or correction requires changing the saved forecast, fit or inputs, terminate this run honestly. A changed analytical decision requires a separately approved future run with genuinely untouched evaluation data; the exposed December holdout cannot be described as unseen for that revised choice.

DSC-10 owns the exact recovery cap; DSC-24 carries it in the approved execution contract. Until both are concrete, a consumer may use an explicitly mocked finite budget but cannot claim integrated recovery acceptance. A bounded code/runtime recheck is not a new business task definition.

Confirmed failed performance is `validation_failed` in conceptual examples; inability to obtain valid scores is `execution_failed`. DSC-24 owns the eventual serialized names. Both route to DSC-29 failure drafting and DSC-30 independent factual/claim verification, then a parent delivery decision. Output-verification failure cannot release an unverified list; exhaust the approved correction budget and deliver a verifiable execution-failure explanation when possible. A blocked verifier cannot be represented as a verified delivery.

The customer explanation says this MVP could not produce a reliable solution with the supplied data/scope, identifies supported limitations or repairable gaps, and never claims the business problem is universally impossible. Validation failure must cite actual measured evidence; execution failure must not invent model scores. Failure variants contain no approved order list.

## Shared handoffs — semantic agreement request to DSC-24

DSC-24 exclusively defines field names, types, serialization, discriminated outcome variants and compatibility. This table is the required surface, not a duplicate schema. The proposed snapshot location is `suiroai/examples/contracts/v0.1.0/`; no example is currently represented as owner-approved or real evidence.

Every cross-component packet needs a contract version, applicable task/run/input/proposal/approval references, producer, artifact identity/version/hash, source lineage, and explicit real/example/mock evidence classification. Distinguish supplied facts, supported interpretations, synthetic assumptions and unknowns. A downstream reference must preserve its upstream mock designation; mocks cannot turn into real evidence by passing through another stage.

| Handoff | Producer → consumers | Required content/binding |
| --- | --- | --- |
| Submission | DSC-25 → DSC-10 | Original request, actual supplied file references, accessibility/missing-file information and source/input versions |
| Proposal/approval | DSC-25 + DSC-10 → DSC-26 | Business goal/output, input snapshot, assumptions/gaps, proposal version, exact approval binding and approval validity; material input changes invalidate it |
| Execution contract | DSC-10 → DSC-26/stage consumers | Same approved task, as-of, allowed actions/artifacts, limits, stage/checkpoint requirements, source versions, temporal isolation and finite recovery policy |
| Preparation result | DSC-27 → DSC-28/parent | Prepared development-data/initial-feature references, row lineage, join/cardinality/quality checks, target/treatment choices, availability metadata, rejected/quarantined data and verified findings |
| Feature proposal/result | DSC-28 internal → parent/evaluation | Definitions/sources, prediction-time timing, training-only fit rule, rationale, prompt/model provenance, generated artifacts and materialization/validation evidence |
| Evaluation/frozen result | DSC-28 → parent/final evaluator | Baseline/candidate metrics, common folds/plan, coverage, selected model/features/preprocessing, immutable freeze references, acceptance rule and separate November 30 forecast |
| Final validation result | DSC-28 → DSC-10/29/30 | Predeclared acceptance rule, actual scores/checks/coverage, frozen/input bindings, parent review, bounded defect-recheck evidence and pass/failure |
| Candidate quantities | DSC-29 numerical module → DSC-30/10 | Arithmetic input references, intermediate calculations, candidate orders and exceptions; not yet approved for reporting/delivery |
| Numerical verification/approval | DSC-30 → DSC-10 → DSC-29 reporting | Independent expected arithmetic/checks and verifier decision, then parent's separate approval tied to the exact quantity artifact |
| Report draft | DSC-29 reporting → DSC-30/10 | Parent-approved quantities and evidence-linked findings with customer wording; failure variant has no valid list |
| Output verification/delivery decision | DSC-30 → DSC-10 → delivery | Independent claim/output checks and exact input/output versions, then parent's separate decision binding the permitted response; never require that later decision as an input to verification |
| Evidence record | All producers → DSC-56/31/9 | Requirement, artifact/version, check, expected/actual result, checker identity/verifier decision, timestamp and real/mock designation |

DSC-24's example set must exercise a complete success chain and branches for inaccessible/missing inputs, stale/rejected approval, equal/worse initial comparison, unsupported plugin/integration, timeout/invalid code/budget exhaustion, final measured failure, permitted defect recheck and exhausted recovery. Include an independently rejected draft and a verified scoped failure response. Examples must reference mutually consistent versions without asserting that fake paths, metrics, orders or checks were produced by execution. A static directory reservation does not unblock consumers; validated owner-published payloads do.

Consumers import the single owner-defined contract surface and pin a known snapshot. A change to serialized structure/meaning requires DSC-24 review and an explicitly versioned migration/snapshot; it must not silently reinterpret an existing approval or artifact. Component-local mocks are allowed only after that snapshot is agreed, with no issue-status changes from mock results.

## Data and leakage boundaries

Canonical active source root: `data/retail_mvp/sales_2022_2025/`.

| Relative input | Meaning |
| --- | --- |
| `supplied_sales/Sales_transactions_2022_2025.csv` | Unchanged raw supplied sales; includes December 2025 future records |
| `supplied_sales/sales_data_dictionary.csv` | Source definitions; Quantity is transaction units |
| `synthetic_inventory/inventory_position.csv` | Synthetic usable-stock snapshots at November 30, 2025 |
| `synthetic_inventory/inbound_deliveries.csv` | Complete synthetic receipt ledger with due dates |
| `synthetic_ordering_rules/ordering_policy.csv` | Synthetic supplier lead times, review, safety stock, multiples and minimums |
| `documentation/synthetic_generation_manifest.json` | Generation assumptions, source hashes and synthetic provenance |
| `documentation/shared_locations.json` | Shared Drive references and source/document identifiers |

Existing documentation reports 18,045 raw rows, 45 exact duplicates, 18,000 distinct records, 28 products, 12 stores and 336 pairs; 336 usable-stock snapshots, 126 incoming lines, 336 policies, with explicit zero open orders for the other 210 keys. These are inspected source facts, not universal input validators or model acceptance results. All operational values remain synthetic and the result illustrative, in `product_unit` as of November 30, 2025.

DSC-27 preserves raw files and logs treatment/lineage for exact duplicates, eight nonpositive quantity rows, transaction statuses and returns/cancellations. Repeated order identifiers may represent legitimate lines. Source completeness is unverified. Global date coverage does not establish zero demand on missing product/store dates; target eligibility/completeness assumptions must be justified and disclosed. Material unknown business facts return through the parent; routine analytical choices remain internal.

`Inventory_Level` is approximate transaction-time stock, not usable stock at review. `Delivery_Days` is customer fulfillment duration, not supplier procurement lead time. Neither substitutes for missing operational inputs. The synthetic ledger's complete zero-open-order statement applies to that ledger only; it does not justify general zero filling. Superseded 2016 workbooks/scenarios are excluded.

The approved execution environment must isolate development and holdout access:

1. Before any feature-generation/model-selection context is built, DSC-27 creates and verifies development references restricted to 2022–2024 training and rolling 2025 validation with every target horizon ending by November 30. Partitioning is post-approval execution, not intake preparation.
2. Feature-generation and model-selection contexts receive only permitted development artifacts, never unrestricted raw future rows or derived future summaries. The existing full-history QA profile/notebook may also reveal December statistics; do not attach them wholesale to modeling/feature prompts. DSC-26 must demonstrate how the actual environment preserves this context boundary; a date-filter instruction alone does not establish compliance.
3. Raw files/holdout are needed for preparation partitioning and later authorized frozen evaluation, outside the feature-generation/selection context. Restricted artifact transfer or separate supported contexts are candidate enforcement mechanisms. Stronger host/filesystem access isolation is preferred where supported, but its feasibility and exact mechanism await DSC-26 evidence; it is not a reason to build a custom runtime. If the supported environment cannot preserve the required context boundary, real execution remains blocked.
4. Fit transformations only on each permitted training fold. Feature definitions carry event/availability time and prediction-time inputs. Development folds, baseline, candidates and acceptance plan are common and recorded.
5. Freeze selection and persist the November 30 forecast before releasing holdout access. Final December evaluation scores fully observed horizons only, reports eligibility/coverage and never retunes. Where missing outcomes prevent justified scoring, report insufficient evidence rather than manufacture zeros.
6. Orders consume the saved November 30 forecast and as-of operational facts. December outcomes cannot alter its fit, selected features, inputs or quantities. Scoring/runtime corrections produce new evidence versions referencing the unchanged frozen artifacts; never overwrite or replace the saved forecast in response to holdout evidence.

These are implementation requirements, not claims that isolation already exists. Inability to enforce them blocks real integration acceptance.

## Replenishment, presentation and independent delivery

The source contract defines the rule: forecast over supplier lead time plus the seven-day review period, add declared safety stock, subtract usable stock and only inbound quantities that arrive in time, clamp net need at zero, then apply minimums/multiples when an order is positive. DSC-29's numerical module implements that rule with traceable intermediate quantities and SKU exceptions. Do not subtract both `On_Order_Qty` and the same receipt lines. Receipt dates cannot cover earlier shortages; stale snapshots require supported intervening movements or an explicit exception. DSC-24 and DSC-29 settle any remaining date-boundary/serialization details without changing this business rule.

The customer list uses `Product_ID`, reliably mapped `Product_Name`, `Store_ID`, `OrderQty`, and `Quantity_Unit`; add needed-by dates only if required by the approved contract. Preserve exceptions and avoid unsupported currency/profit optimization. `reporting/` consumes parent-approved quantity artifacts and evidence-linked findings; focused humanization may change wording but cannot calculate, round or alter numbers.

DSC-30 independently recomputes expected quantities from bound source inputs and policy and checks claims against measured artifacts. It cannot accept the producer's own passed flag as proof or merely call the same calculation function for the expected answer. It verifies success and failure drafts, units, synthetic disclosures, scope, leakage evidence and approval/version bindings. The parent alone authorizes delivery. One report/explanation is the customer output; code, notebooks, internal profiles and evidence remain internal artifacts.

## DSCraft reuse without modifying the library

The following symbols exist in the inspected checkout; suitability for this case still requires component-level execution evidence. No dependency or new public API is implied.

| Verified local surface | Candidate use | Constraint |
| --- | --- | --- |
| `dscraft.eda.LazyEDA().profile(source)` in `packages/dscraft/src/dscraft/eda/` | Internal prepared-data schema/null/quantile/cardinality/association profiling | Does not decide sales semantics, joins or availability safety; optional HTML remains internal |
| `dscraft.forecast.ForecastConfig`, `forecast`, `backtest` in `packages/dscraft/src/dscraft/forecast/` | Classical baseline/candidates and metric helpers, including naive/seasonal-naive/intermittent demand options | Existing backtest takes last N observations per series, not the required calendar folds. `forecast()` refits per call; not a frozen-model artifact interface. Its ID/date/target path is not LLM-feature materialization |
| `dscraft.automl.build_model(name, "regression", **kwargs)` in `packages/dscraft/src/dscraft/automl/models.py` | Construct unfitted XGBoost/LightGBM/CatBoost estimators for a bounded shortlist when justified | Application owns fit, temporal evaluation, feature materialization and freeze |
| `dscraft.core.data` | Optional Arrow/Polars conversion | No SuiroAI task/run/approval contracts |

`dscraft.clean.Sanitizer` concerns classification-label/contamination auditing, not general retail cleaning. `dscraft.agent` is a bring-your-own-callable benchmark, not a Codex/Data connector. Do not reuse those names to imply unsupported functionality. Architecture/roadmap tables are not exported APIs. SuiroAI owns the business semantics and orchestration; it requests no DSCraft changes here. Prefer selective extras if installed; do not bring in all stacks or neural representation training for this MVP.

## Actual Codex/Data execution boundary — DSC-26 acceptance wait

DSC-26 receives the same approved execution contract and returns genuine capability/outcome/evidence packets. It does not redefine the task, own parent transitions, duplicate preparation/modeling logic or supply customer consent. The handoff is a semantic boundary; this document deliberately does not prescribe an invented `execute()` transport, external `@Data` endpoint, remote filesystem path or Code Interpreter replacement.

Before real integration can be accepted, DSC-26 must identify and demonstrate:

| Evidence prerequisite | What the consumer needs |
| --- | --- |
| Supported host and invocation | Actual plugin-enabled Codex/Data environment, invocation mechanism, versions/permissions and bounded engineering probe |
| Task/file transfer | Exact approval/contract and readable input-version mapping, no ambient customer files or implicit fixture substitution |
| Isolation and checkpoints | Enforced development/holdout separation; parent can inspect required stage evidence before progression; supported pause/resume or staged invocation behavior without losing the same task |
| Real result retrieval | Actual code/config, logs, calculations, metrics, artifacts and identity/hash references, not prose or an example packet |
| Failure/limits | Distinct unavailable plugin, unsupported integration, missing material facts, invalid code, timeout, exhausted budget and inaccessible artifact outcomes; evidence of actual cancellation/limit behavior |
| Dependency/environment feasibility | Compatible Python/DSCraft extras and artifact persistence/retention; no assumption that the host can install local sibling packages |

The actual DSC-26 owner has now published discovery commit `455a215` on its local component branch, with ownership acknowledgment and two genuine startup probes. Codex CLI `0.163.0` app-server exited 1 before initialization: default SQLite state initialization failed; a writable-state retry reported “Operation not permitted” without identifying its underlying operation. No Data skill discovery/attachment, analytical execution, retrieval or cancellation was reached. DSC-3 agrees the semantic boundary and reviewed the evidence; the actual transport is still unverified. See [COORDINATION.md](COORDINATION.md) for exact worktree/paths. This host blocker is neither measured model failure nor evidence that Data is missing or universally unsupported.

Installed plugin instructions and local library source remain insufficient. A genuine manual invocation in a verified Codex/Data host may establish limited capability evidence; it does not establish automated handoff, isolation, checkpoints, cancellation or end-to-end acceptance. Prose, local manual calculations, mock adapters and Code Interpreter substitution cannot establish the requested integration. Unsupported or unverified capabilities remain explicit blockers.

## Evidence, integration sequence and acceptance

Every producer retains requirement-linked artifacts with source/task/run/input/proposal versions, checks, expected/actual outcomes and verifier decisions. Stage artifacts live in producer-owned namespaces under `suiroai/artifacts/<task-id>/<run-id>/`; DSC-10 owns checkpoint indexing in run state, DSC-24 owns the record type, DSC-56 owns fixed acceptance mapping, DSC-31 owns recording/index capture. This needs no generic evidence service or autonomous verifier runtime.

Parallel consumer coding is allowed after DSC-24 publishes the agreed versioned examples and ownership is acknowledged. Genuine execution proceeds in customer step order. Integration then checks actual intake approval → supported adapter → preparation → initial comparison → required LLM features → bounded selection/freeze → unseen result → quantities → independent verification → one delivered report or scoped failure. DSC-31 records only a working integrated flow; DSC-56 audits current real evidence; DSC-9 requires child acceptance and a named reviewer. Failure-branch tests do not replace the successful full-input demonstration.

Architecture coverage has been reviewed by three read-only DSC-3 subagents against the contracts, library and workflow. Actual DSC-24/26 layout/path acknowledgments and DSC-26 semantic boundary agreement are separately recorded; neither review nor acknowledgment is execution acceptance. Outstanding blockers are the reviewed DSC-24 snapshot, supported DSC-26 invocation and context-boundary/checkpoint evidence, and unimplemented downstream components. The minimal foundation is backed up on `codex/dsc-3-mvp-architecture` in the new private `SuiroAI/suiroai` repository. No Linear status, Miro board, merge, deployment or customer delivery has been changed. Source backup is not an MVP acceptance signal.
