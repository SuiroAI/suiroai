# DSC-30 independent verification and permitted delivery

This component consumes the DSC-24 `0.1.0-draft.3` handoff and independently checks DSC-29 quantities and customer drafts. It uses immutable measured source bytes, separate arithmetic and trusted independent semantic reviewers. Producer pass flags do not establish verification. The parent remains responsible for current state, checkpoint decisions and permission to publish.

The implementation lives in `src/suiroai/verification/`; tests are in `tests/verification/`. It introduces no application, hosting, dashboard, autonomous runtime agent or external `@Data` API. Supported analytical execution remains DSC-26's responsibility. Development coordination and outstanding acceptance waits are recorded in [COORDINATION.md](COORDINATION.md).

## Source reconciliation

`arithmetic.reconcile_orders(orders, exceptions, *, scope_keys, forecast_rows, inventory_rows, receipt_rows, policy_rows, name_rows, as_of, ledger_complete, receipt_timing)` independently derives the expected order and compares each candidate intermediate. It returns checks, independently discovered per-key exceptions and expected orders. Decimal arithmetic preserves fractional forecasts and exact minimum/multiple handling; decimal evidence values serialize as strings.

The checks cover:

- Exact namespaced Product_ID/Store_ID identity, unique scoped output and source coverage, and supported product names available at the review date.
- Daily forecast coverage throughout supplier lead time plus review period; forecast origin, information availability, dates and `product_unit` consistency.
- One usable-stock snapshot at the review date, applicable purchasing policy, safety stock and compatible units. Transaction `Inventory_Level` is not used as usable stock; customer `Delivery_Days` is not supplier lead time.
- Ledger-wide purchase-order line uniqueness, positive incoming quantities, Order_Date/Expected_Arrival_Date chronology and eligibility within the protection horizon.
- Reconciliation of the complete detailed incoming ledger with the inventory open-order summary. Only eligible receipts reduce need; the summary is never subtracted again.
- Zero clamping, positive-order minimum, upward rounding to an order multiple and equality of approved quantities to independently computed quantities.
- Daily stock sufficiency before existing receipts and the candidate order arrive. Conservative within-day handling withholds a quantity when avoiding a shortage depends on assuming an arrival precedes that day's demand.

Each scoped key must have a reconciled order or an evidenced, explicitly withheld exception. Missing, stale, ambiguous or inconsistent sources never become an implicit zero or silently dropped key. An honestly withheld exception can pass verification of the report while its underlying source/timing problem remains unresolved. The customer narrative reviewer must also confirm that the stated exception accurately describes the evidence.

Numeric candidate checking sets `require_product_names=False`: an ID-only candidate may omit an unbound display name or use the contract-valid null value. Any non-null supplied name is independently checked. Final report checking requires a reliable name as requested for this assignment; absent or conflicting mappings remain explicit exceptions. Reissue and independently check a named candidate before parent quantity approval, since draft.3 requires approved/report order rows to preserve the checked candidate content.

`engine.SourceReaders` is an explicit application adapter supplied by trusted code after agreement with source owners. It is not a new shared schema. Operational inputs use their existing CSV headers plus the configured source namespace. Forecast readers return rows with `key`, `date`, `quantity`, `quantity_unit`, `as_of_date` and `latest_information_available_date`. Scope readers return exact contract keys; name readers return `key`, `product_name` and `latest_information_available_date`. There is no default forecast parser or aggregate-to-daily interpolation. A forecast without the required daily evidence must not be silently expanded.

The engine permits `receipt_timing="unknown"`, using the conservative treatment above. The low-level reconciler also exposes a `before_daily_demand` option for explicitly reviewed use, but the engine rejects it because this MVP supplies no approved alternative within-day convention. Real synthetic-scenario verification also checks the current generation manifest, review date, counts, file hashes and synthetic operational provenance. Ledger absence means zero only under the authenticated complete-ledger assertion; sales-date absence receives no such inference.

## Claims and full customer text

`claims.check_claims(report, *, resolve_bytes, review_claim, review_narrative, verifier)` returns shared check dictionaries. The report must first pass shared record validation. `resolve_bytes(ref)` must verify the immutable reference and return actual bytes; the existing integration `ArtifactStore` provides this boundary. Every report reference is resolved before full narrative review. Every declared claim and every `final_report` finding receives independent review against its referenced bytes.

The parent supplies the following callbacks as trusted independent application code, never from producer JSON or an executable artifact:

| Callback | Inputs and obligation |
| --- | --- |
| `review_claim(item, evidence_bytes)` | Detached claim/finding and tuple of actual bytes in reference order; verify the statement against the underlying evidence, not merely another assertion or producer check. |
| `review_narrative(report, evidence_map)` | Detached full report and measured bytes keyed by `(artifact_id, version, sha256, provenance)`; inspect every material statement, including undeclared prose, quantities, identities/names, exceptions, findings, limitations and synthetic provenance. |

Both return exactly `{"status": "pass" | "fail" | "unavailable", "expected": <nonempty string>, "actual": <nonempty string>}`. Missing callbacks, retrieval failures, exceptions, booleans, unknown statuses or empty observations cannot pass. There is no automatic keyword-based semantic approval. The caller must establish reviewer independence and capability; a configured identity string alone does not prove either.

For terminal drafts, structural checks reject orders and quantity-result references and require the declared scope limitation. The independent narrative reviewer must verify that the delivered explanation is specifically about this MVP and the supplied data/scope, does not claim universal impossibility, invent measured underperformance or substitute a runner-up after final failure. Execution failure requires the exact parent-reviewed failed stage; measured validation failure requires the current frozen failed evaluation and concluded parent review. Failure explanations do not require successful quantity artifacts.

An execution explanation may cite the immutable failed-stage artifact rather than duplicate that stage's internal log references. Its stage, reason and error category must still match exactly; its evidence references must remain within that stage's evidence chain. Either the failure evidence or a separate report decision must identify the exact stage reference. The report may reuse the stage's authenticated concluded decision, avoiding circular self-references and an unnecessary new terminal review. Scoped customer wording still receives independent semantic review.

## Preexecution guidance

`guidance.check_capability_guidance(submission, proposal, customer_text, *, resolve_bytes, review, verifier)` handles the shared missing-input snapshot consisting only of submission and proposal. It validates both records, source access/provenance, actual accessible source bytes/hash/size, exact submission reference and input/proposal digests, and material gaps/readiness. It rejects a fabricated run identity and never creates an execution contract or approval.

The trusted reviewer receives `(text, submission, proposal, evidence_map)` and returns the same strict review result described above. It must check the exact unsupported decision, minimum business facts needed, consequences and next step; an optional narrower task must be offered explicitly without silently replacing the goal. Statistical-method questions, unsupported capability claims, invented quantities and hidden provenance must be rejected. Missing or inaccessible files are disclosed snapshot declarations, not files this module claims to have read. The caller remains responsible for the current authoritative snapshot and genuine access evidence.

Draft.3 `output_verification` requires an approved binding/run; preexecution missing-input snapshots do not have one. Guidance therefore returns shared checks bound to submission/proposal rather than fabricating those fields. DSC-25/DSC-10 own publishing this guidance through the existing conversation. It is not an execution-derived final report or standalone delivery authorization.

## Parent approval and delivered content

`engine.OutputVerifier` reads an authoritative current handoff through `ArtifactStore`. The parent supplies all current record/artifact references and an `authenticate(records, raw_artifacts)` callback returning literal `True` only after checking currentness, permission, provenance and verifier independence. A producer-selected subset, highest version in an incomplete subset or claimed parent actor string is insufficient. Recreate the verifier when parent state changes; immutable byte hashes do not establish freshness or authority by themselves. Mocks are refused by default; `allow_mock=True` enables component examples only.

The sequence avoids circular approval evidence:

1. `check_candidate(candidate_ref, readers=..., evidence_id=..., verified_at=...)` measures source arithmetic and stores independent `evidence_record` evidence against the exact unapproved candidate version. Candidate approved quantities and parent decision are null.
2. DSC-10 reviews that evidence and produces the next approved quantity version, referring to the earlier candidate. Inputs, intermediates, names and exceptions remain unchanged; the report consumes the exact approved version.
3. `verify_draft(report_ref, verification_id=..., readers=...)` performs current-binding, arithmetic and claim checks and stores check-only `output_verification`. It always returns `blocked`, null parent decision and no customer response, including when checks pass.
4. DSC-10 reviews the checks and authorizes the exact report and check-only reference. `propose_delivery(verification_ref, parent_decision=..., readers=...)` reruns checks and returns the next verification version as a proposal. The parent/adapter authenticates and persists it; this function does not grant permission itself.
5. `deliver(verification_ref, authorize=..., publish=..., readers=...)` reauthenticates the snapshot, reruns/reconciles checks and requires literal current parent authorization. No extra customer sign-off is introduced. `publish(approved_utf8_bytes)` uses the existing output surface and returns `{"reference": <nonempty string>, "content": <actual readback bytes>}` from that surface.

The agreed parent integration registers the blocked check-only result through DSC-10's `register_verification_check(ref)` and retains it as measured external evidence. Do not include both verification versions as current records: draft.3 permits one current output-verification record. The parent stage-release allowlist must include the actual prior check bytes before final integration can proceed.

Delivery requires readback bytes exactly equal to the approved customer draft. The returned receipt includes verification/report references, delivered-text artifact/hash, `delivery_evidence_ref` for a typed measured check, destination reference, verification time, mock designation and preserved unresolved exceptions. Changed checks, source bytes, report text, parent permission or readback prevent a verified-delivery claim. A readback failure can be observed after a publisher has written; its exception exposes `evidence_ref` for the persisted rejected check, and the caller must not describe that failure as verified delivery. This component creates no external transport.

The store reserves a fresh evidence namespace before invoking the publisher, so duplicate or concurrent use of the same delivery grant cannot publish twice. A failed or interrupted attempt retains that reservation; any further attempt requires a new parent-reviewed verification version. This module has no automatic retry loop.

## Verification evidence and remaining waits

Run component and shared-contract regressions from the application root:

```sh
PYTHONPATH=src python3 -m pytest tests/verification -q
PYTHONPATH=src python3 -m pytest tests/contracts -q
```

Meaningful examples exercise arithmetic/receipt timing and coverage errors, names/units/provenance, stale bindings, false metric claims, adulterated undeclared prose, unavailable evidence/reviewers, truthful guidance, failed validation disguised as success, exact execution-stage failure evidence, parent veto, changed evidence between checks and permission, and altered delivered readback. These are explicitly mocked component tests; they do not demonstrate analytical model performance, genuine supported Data execution or a completed customer delivery.

Real acceptance still waits for genuine DSC-29 artifacts and genuine preparation/feature/model evidence, current DSC-10 final-validation and quantity approvals, authenticated independent semantic reviewers/source readers, the supported DSC-26 execution boundary and actual output-surface readback. Native blockers and upstream issue status are not cleared by these examples. No real customer run or issue closure is claimed here.
