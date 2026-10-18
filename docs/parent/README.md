# DSC-10 parent workflow and guardrails

This component controls one approved retail restocking task. It owns proposal/approval bindings, stage permissions, checkpoint adoption, bounded internal review and final response authorization. It does not inspect customer files, prepare data, fit models, calculate orders, compose reports or implement a Codex/Data host.

Development uses `nightly` commit `83f134fb7674de64d7f3a6b62f984bb6486ec81d` and DSC-24's unchanged `0.1.0-draft.3` contracts. See [coordination and blockers](COORDINATION.md), the [contract snapshot](../contracts/SNAPSHOT.json), and [exclusive ownership](../architecture/OWNERSHIP.md). Mock component checks do not establish genuine integration or MVP acceptance.

## Transition rules

| Current state or event | Permitted next state | Guard |
| --- | --- | --- |
| Submission received | `intake` | Measured accessible references and valid submission/input digest; replacement material input must have the same task ID and a newer input version. Receiving data performs no preparation. |
| Proposal presented | `awaiting_approval`, or proposal readiness/guidance state | Exact current submission and valid proposal digest/binding. A correction requires a newer proposal version and invalidates prior approval and outstanding permission. |
| Pending response | `awaiting_approval` | Silence grants no execution permission. |
| Rejection | `intake` | A revised proposal must be presented before approval can be recorded. |
| Approval recorded | `approved` | Exact current proposal/material input binding plus trusted intake authentication. |
| Approved execution started | `preparation` | Execution contract preserves the approved task/source assumptions and carries required actions, finite limits and a previously unused run ID. |
| Preparation passed | `initial_baseline_evaluation` | Typed preparation, lineage/availability and passing checkpoint evidence. This stage covers preparation, EDA and initial features. |
| Initial result is better | `llm_features` | Measured comparable baseline/candidate result and adopted parent checkpoint. |
| Initial result is equal or worse | `initial_review` | No automatic advancement. Bounded internal evidence review may permit the required additional-feature stage or terminate the run. |
| Additional features passed | `comparison_and_freeze` | Feature proposal/result and materialization/validation evidence; definitions remain within the approved bound. |
| Comparison passed | `final_validation` | Eligible bounded shortlist and immutable selected model/features/preprocessing, evaluation/acceptance references and saved November 30 forecast. |
| Final validation passed | `recommendations` | Exact frozen choice and reserved unseen data; measured predeclared acceptance gates and adopted parent review. |
| Final validation failed | `final_review` | No recommendations. Internal source/split/model/metric/runtime evidence review is required. |
| Demonstrated scoring/runtime defect | `final_validation` | Explicit prior parent authorization, remaining stage/recheck/review/time budgets, unchanged frozen choice/forecast/threshold/chronology and preserved recheck history. |
| Confirmed underperformance, unresolved review or exhausted recovery | `failure_reporting` | Terminal outcome; no second-ranked-model fallback, holdout tuning or further selection loop. |
| Recommendations/report passed | `output_verification` | Approved quantities and draft are bound to the passed final validation and independently checked evidence. |
| Verified report or failure explanation | `delivery_ready` | Exact draft/version, passing independent checks, trusted parent adoption and an outcome-appropriate permitted response. |
| Verification fails or its remaining budget is exhausted | `delivery_blocked` | Terminal internal blocker; no unverified customer response and no reopening loop. |
| Response taken | `delivered` | One response only. No routine analytical progress is returned through this API. |

An execution result containing material facts/input gaps returns to intake and revokes approval only after trusted parent evidence review confirms an irreducible consequential fact or material contract change. A worker cannot relabel an algorithm choice as a customer question. Routine analytical choices remain internal. An execution error is distinct from measured model underperformance and from missing-data guidance. Failure reports contain no recommendation list and describe this MVP's inability to produce a reliable solution with the supplied data/scope; they cannot claim universal impossibility.

## Consumer API

Import `ParentWorkflow` and `GuardRejected` from `suiroai.parent`. The constructor accepts the DSC-26 artifact store, three trusted callbacks, an optional clock and `allow_mocks=False` by default.

| Call | Meaning |
| --- | --- |
| `receive_submission(submission, external_refs=...)` | Measure and record the supplied snapshot; invalidate affected proposal/approval. Replacing input during dispatch requests cancellation and rejects replacement until that dispatch has finished. |
| `present_proposal(proposal)` | Record the exact intake proposal or missing-data guidance; revoke approval and issued permission. |
| `record_approval(approval)` | Record pending/rejected/approved consent against the exact current proposal. |
| `start(execution)` | Start the same approved task under one bounded execution contract. |
| `issue_stage(released_input_refs, seconds=60)` | Measure and review an exact nonempty input allowlist; issue one outstanding immutable stage request with remaining limits, deadline and output namespace. |
| `execute(request_ref, work_root=..., host=None)` | Dispatch only the outstanding request through DSC-26 `StageAdapter`; validate and adopt its committed result before advancing. A supplied mock host is component-test infrastructure. |
| `parent_permits(request_ref)` | DSC-26 permission callback. Accept the exact outstanding request once, before cancellation/expiry; JSON permission claims are insufficient. |
| `parent_review(candidate, artifact_bytes)` | DSC-26 private candidate callback. Review measured output bytes and exact checkpoint/prior-authorization claims; return a candidate-specific attestation without advancing state. |
| `review_initial(evidence_refs, proceed=...)` | Resolve the initial equal/worse branch through bounded internal evidence review. |
| `review_validation(evidence_by_domain, verdict=..., defect_kind=...)` | Require all five evidence domains; authorize only demonstrated bounded scoring/runtime correction or terminate. |
| `prepare_failure_delivery()` | Open failure drafting/verification after a terminal failure. It cannot enable recommendations. |
| `register_verification_check(ref)` | Register one authenticated DSC-30 check-only record for the exact current report as measured external evidence. It grants no delivery permission; the final proposal must cite that check and report. |
| `cancel()` | Revoke pending dispatch/delivery permission. A completed delivery remains historical. |
| `take_response()` | Return the exact independently verified response once, only from `delivery_ready`. |
| `state`, `checkpoint()` | Inspect current state and a defensive copy of its private checkpoint. Neither accepts worker-authored state. |

Preparation releases must satisfy the [open development-partition integration gate](COORDINATION.md#open-integration-gates). The current shared draft does not yet permit the safe DSC-27 derived development release needed for genuine native preparation. Do not treat a controller-approved raw release as permission to expose December rows to a native development task.

## Permission and evidence boundary

The trusted callbacks are supplied by the controller process, never by worker JSON:

- `confirm_approval(approval, proposal)` authenticates actual intake consent for the exact proposal.
- `review_release(stage, refs, records)` independently verifies measured content, permitted use and chronology. Schema-valid availability claims alone do not establish temporal isolation.
- `review_evidence(packet, artifact_bytes)` independently decides whether actual checkpoint/recovery/delivery evidence supports the claimed decision. It receives candidate packets or internal review packets; it must inspect their meaning rather than return a constant success in real integration.

Each callback must return literal `True` to allow, remain bounded and avoid parent mutations. `True` lambdas in component checks are explicitly mocks. The parent does not infer customer consent, independent verification or reliable analytical outcomes from a schema-valid document. Stage workers may propose checkpoint decisions; only the trusted candidate review can adopt their exact claims. A defect recheck additionally requires an authorization already recorded before that request was issued.

Preparation, initial evaluation, feature generation and comparison cannot skip failed/unavailable checkpoint checks. Development stages release only independently reviewed development artifacts with information/event dates through November 30, 2025. Final validation requires the exact reserved artifact after the freeze. The selected model, features, preprocessing, acceptance rule, chronology and saved November 30 forecast cannot change during recovery.

## Bounds, failures and persistence

The execution contract controls stage attempts, candidates, feature definitions, internal reviews, defect rechecks and total execution time. `start` checks the action permissions needed for this fixed workflow. Ordinary stage time is reduced by a small failure-verification reserve: `max(1, min(30, max_execution_seconds // 5))` seconds from the original allowance. Output verification can consume that reserved remainder; the reserve does not enlarge the approved total. Once the total deadline itself has passed, native verification cannot dispatch under an invented extension.

Controller-owned stop receipts preserve typed failed-stage evidence for cancellation, denied internal progression, exhausted bounds and dispatch exceptions. Their evidence bytes explicitly state `native_execution_claimed: false`; they describe a parent permission/checkpoint stop, not a claim that a native turn ran. Actual native activity must be established by DSC-26 receipts. Failure drafting and independent verification still have to validate those receipts and the exact terminal classification before any explanation is delivered.

Records and event payloads are stored as immutable version/hash-bound artifacts. Events include the current context reference, outcome and authoritative counters. This implementation supports in-process pauses for approval, review and outstanding stage results. `checkpoint()` is inspectable state, not an authenticated restore format. There is no process-restart recovery, replay loader or durable resume claim; adding one requires DSC-10-owned design and genuine integration checks rather than accepting serialized worker state.

No LangGraph dependency or reusable workflow platform is introduced. The finite in-process controller is limited to this task. DSC-3 owns any future shared dependency decision.

## Component evidence and genuine acceptance

[Transition checks](../../tests/parent/test_workflow.py) use clearly marked invented packets from the pinned DSC-24 examples, the actual DSC-26 adapter and a mock host. They exercise approval/version invalidation, single-use dispatch permission, failed checkpoint rejection, chronological input restrictions, initial-result branches, bounded final review/recovery and permitted final/failure delivery. Review the [DSC-10 evidence report](EVIDENCE.md) for the exact command, final test count and any limitations; this document deliberately does not freeze a moving test count.

Every typed checkpoint record needed downstream must appear in the committed stage result's `output_refs`; stored manifest entries alone do not count as accepted outputs.

These checks establish component guard behavior only. They do not show real customer consent, source preparation, LLM-generated features, genuine Data execution, unseen validation, arithmetic/claim verification or actual customer delivery. Real acceptance waits for the native host and genuine component artifacts, the safe preparation release contract, cross-component integration and the named acceptance owners. No Linear issue status is changed by passing mocks.
