# DSC-56 architecture and evidence review

Reviewer: **DSC-56 architecture-review subagent**, October 18, 2026. Reviewed
application source at nightly `7af5a855ea98a47d332b2428bc1325f8154eb49e`.
Refreshed against nightly `93f6cc9f7725ae0d9d5442bd64491c007f4d372c`;
its additional DSC-31 preparation documents/templates were read before final
evidence recording and contain no completed demonstration.
This is a source review for the fixed retail case, not an actual DSC-3 owner
acknowledgment, completed analytical audit, customer approval or issue closure.
The checklist/evidence ledger records current Linear retrieval separately;
this review uses the assignment's embedded requirements and repository evidence.

## Owned paths and interface

The architecture owner's published [ownership map](../architecture/OWNERSHIP.md)
reserves exactly `tests/acceptance/`, `docs/acceptance/` and
`evidence/acceptance/` for DSC-56 (relative to this application repository).
These paths remain suitable for fixed checks, a small evidence ledger and named
reviewer decisions. They require no application runtime, reusable audit platform,
shared test helper or dependency. DSC-24 owns schemas and evidence-record types;
DSC-10 owns parent authority, workflow and recovery. DSC-3 owns common tooling.
DSC-56 must report owner defects instead of repairing those shared areas here.

The reviewed development contract remains `0.1.0-draft.3`, originating at
`dd3e0dda1b759ebe5439e78e8cf10e3374eb700b`, with release ACKs recorded in
[architecture coordination](../architecture/COORDINATION.md). Validate current
bytes against [the exact snapshot](../contracts/SNAPSHOT.json). Published
development allocation does not grant genuine execution or final acceptance.

## Concrete discrepancies and uncovered proof

| Finding | Evidence and consequence | Required owner evidence/action |
| --- | --- | --- |
| Safe derived preparation release is unresolved | [Parent open gates](../parent/COORDINATION.md#open-integration-gates) and [preparation interface](../preparation/INTERFACE.md) document that draft.3 rejects the derived development artifact while the parent permits approved source references. Raw sales includes December; releasing it to native development is unsafe. | DSC-24/3 agree versioned derived lineage/release semantics; DSC-10/26/27 implement and prove the actual approved path. Keep final audit blocked. |
| Genuine demand and historical availability are unestablished | [Source reconciliation](../contracts/audit/source-semantics.md) shows sparse per-key dates and unknown retrospective status/return timing. [Modeling interface](../modeling/INTERFACE.md) requires genuine completeness and target-availability evidence; missing horizons stay unavailable. | DSC-27/28 justify treatment, population, observed horizons and information timing with actual evidence. Do not manufacture zero days or availability dates to obtain scores. |
| Step-7 derived context release remains an integration gate | Parent coordination requires an owner-agreed registration path for derived task/EDA/error summaries and upstream typed records. Immutable preparation cannot be retroactively amended to accommodate new summaries. | DSC-24/10/26/28 prove current versioned release and real LLM prompt/response lineage after step6, without December input. |
| Numerical approval and independent verification transport are incomplete | [Replenishment integration](../replenishment/INTEGRATION.md) requires the same-task numerical check/parent approval/resume before humanizing. Parent coordination lists safe native release of the external check-only artifact and failure-draft staging as needing a bridge. [Verification coordination](../verification/COORDINATION.md) also requires authenticated parent/source reviewers. | DSC-10/24/3/26/29/30 demonstrate numerical approval before wording, exact checked draft, current parent adoption, response authorization and actual readback. Test callbacks are not independent authority. |
| Component evidence is not a coherent real run | [Modeling component evidence](../modeling/COMPONENT_EVIDENCE.json) explicitly has `evidence_mode: mock`, no real LLM call, separate feature/model fixtures and an aggregate forecast lacking daily trajectory. Preparation and parent documentation likewise mark mock consumer runs. | Supply one task/run/version-bound actual chain. Reconcile real metrics, feature contribution, daily forecast and approved quantities; do not assemble unrelated mock successes into a demonstration. |
| Native engineering success has bounded scope | [Isolation review](../integration/ISOLATION_PROBE.md#actual-isolated-data-pass) retains actual synthetic Data execution and denials. It explicitly leaves full adapter/customer execution, negative patch permission and other scopes unverified. Earlier architecture discovery notes are historical, not the latest capability conclusion. | DSC-26 provide current relevant customer-stage receipts and effective guardrail evidence. Neither old discovery failure nor later synthetic success substitutes for the integrated run. |
| Recording and real final chain are absent from the reviewed tree | [Demo preparation](../demo/README.md) and [capture evidence status](../../evidence/demo/README.md) contain instructions and an unfilled index only, explicitly no completed recording or run. Correct terminal failure handling proves that failure path only. | DSC-31 provide actual recorded demonstration plus artifact index and hashes. DSC-56 separately reviews actual success or failure honestly; successful restocking remains unproven without its genuine evidence. |

These are acceptance blockers or explicit evidence limitations. Current-source
review found no basis to weaken their gates.
The parent frozen-bundle release was already corrected in the current source;
the older modeling-interface paragraph describing its missing allowlist is
historical and must not be treated as a still-open defect without rechecking
[the current parent handoff](../parent/COORDINATION.md#frozen-bundle-release-follow-up).

## Reproduced finding-identity discrepancy

The new `test_mock_unmodified_shared_findings_collide_after_real_report_composition_and_block`
passes the shared `successful_analysis.json` findings through the actual
`draft_success` producer and independent `OutputVerifier.verify_draft` consumer.
Preparation, feature, evaluation and final-validation records reuse the
source-local `finding_id` value `mock-finding`. Shared record validation permits
these upstream records and the composed report. Composition retains those IDs,
but the independent `claims-unique-identities` check rejects the report:
**18 declarations, 15 unique identities**. Delivery remains blocked.

This is a reproduced contract/composition compatibility discrepancy on marked
mock inputs, not a demonstrated real customer failure or proof of a numerical
error. The actual DSC-27 producer uses `preparation-*` IDs; DSC-28's record APIs
accept supplied findings, so source-local uniqueness cannot establish globally
safe composition. The independent verifier's rejection is the correct behavior.

Concrete owner request: **DSC-29 with DSC-24/3** should agree source-qualified
finding identities, or namespace findings during composition while retaining
their immutable source/evidence references. **DSC-30** must enforce that agreed
rule. This DSC-56 branch changes none of those owned files. Separate positive
mock report checks explicitly namespace finding IDs by source artifact before
rehashing; the unchanged shared-example regression remains blocked. No fix or
real acceptance is inferred from the positive examples.

Affected recheck: source findings → report composition → independent identity,
claim and narrative checks → exact draft approval/delivery. Preserve unaffected
quantity/model evidence. Link the corrected contract/report versions and rerun
the failing composition and affected report tests, without restarting modeling.

## Required fixed verification scope

Each check must bind its source requirement, actual artifact/version/hash,
expected behavior, observed outcome, evidence mode and named verifier decision.
Positive mocked fixtures establish check development only. Use adversarial
mutations to show rejection, alongside the relevant component checks:

| Risk | Required observation |
| --- | --- |
| Approval/version bypass; premature joins | Silence/rejection, superseded proposal/input and reused request do not dispatch. Intake performs receipt/read-only inspection only; preparation begins with exact current approval. |
| Duplicate/grain errors and sparse dates | Measure raw versus distinct rows, source lineage and unique operational keys. Unknown per-key days are unavailable; eight nonpositive source observations require documented treatment, not automatic future-input rules. |
| Leakage and source semantics | Future-poisoned rows cannot change development features/selection. Training target horizons finish by November30; final holdout is released after freeze. Customer `Delivery_Days` and approximate `Inventory_Level` cannot replace synthetic procurement policy or usable stock. |
| Steps6/7/8 and bounded selection | Initial comparable baseline evaluation precedes actual LLM feature definitions/materialization; bounded common-plan comparison precedes immutable freeze. No arbitrary feature-field or learned-transform timing assertion suffices. |
| Step9 review/recovery and terminal behavior | Five-domain internal parent review distinguishes measured underperformance from execution failure. Only demonstrated scoring/runtime correction gets prior bounded authority. Model, features, preprocessing, rule, forecast and chronology remain unchanged. Failed/exhausted/unresolved recovery terminates without recommendation, second-best selection or another tuning loop. |
| Receipts and arithmetic | Independently remeasure dated receipt lines, conservative within-day timing, pre-arrival shortage, policy horizon, minimum/multiple rounding and exception scope. `On_Order_Qty` reconciles lines and is never added again. Aggregate-only forecasts cannot invent daily quantities. |
| False claims, delivery and stale evidence | Check full narrative and numerical claims against actual independent evidence, exact current quantity/report versions and current parent permission. A terminal explanation is scoped to this MVP/data, carries no purportedly valid list and claims no universal impossibility. Missing/stale files or wrong versions block acceptance. |

## Affected rechecks after correction

Preserve unaffected decisions and immutable historical evidence. Do not rerun the
whole workflow merely because a result changed; identify the changed dependency
and retain the correction reason, previous/next versions and reviewer decision.

| Changed dependency | Minimum affected recheck set |
| --- | --- |
| Approval, input, proposal or material task facts | Approval bindings, stale permission rejection and all dependent execution artifacts; new material facts return to proposal rather than a holdout recheck. |
| Shared release/availability representation | Snapshot and contract validation, parent release policy, adapter isolation/transport and every consuming preparation/feature/final-verification handoff that changed. |
| Preparation, grain, target or chronology | Source reconciliation, affected joins/lineage/availability and all dependent features, fits, frozen results, scores and quantities. Do not call this a bounded frozen scorer correction. |
| Demonstrated scoring/runtime defect after freeze | Parent prior authorization/budgets, corrected scorer/execution evidence, unchanged complete frozen dependency hashes, reserved population/coverage, affected scores and final parent decision; then dependent quantity/report verification only if permitted. |
| Receipt/policy/daily forecast or quantity draft | Timing/double-counting and affected arithmetic/exception checks, exact approved quantities, every dependent report claim and delivery authorization. A frozen forecast correction is not permitted as step9 recovery. |
| Narrative-only correction | Affected factual/limitation checks, exact draft hash/version, independent verification, parent authorization and output readback. Retain unaffected arithmetic evidence. |
| New run, stale source hash, contract revision or new DSC-31 recording | Rebind current affected artifacts and reviewer decisions, remeasure integrity and chronology, and re-audit recording-to-run identity. Keep unrelated validated dependencies intact. |

Final acceptance remains pending genuine run artifacts, DSC-31 recording and
current DSC-24/10 contract/guardrail evidence. No parent milestone or missing
criterion is waived by this source review.
