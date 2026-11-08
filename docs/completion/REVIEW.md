# DSC-9 MVP completion review

**Decision: Blocked — milestone acceptance withheld.** Reviewed October 18, 2026 against `origin/nightly` commit `c91ea224af2f8932e06027baad228ca469fb85e2`. Reviewer: **Codex DSC-9 reviewer (/root)**. Independent read-only reviews: **evidence_review**, **closure_review**; regression verifier: **regression_review**. These identities record the actual review; no human/owner acceptance is inferred.

The application has substantial component implementation and real isolated synthetic Codex/Data engineering evidence. It has no evidenced successful selected-case preparation→modeling→validated recommendation→final-report demonstration, DSC-31 recording, or passing DSC-56 final audit at this revision. No genuine failed customer/model run was executed in this review either: its runtime outcome is **not executed**, not `validation_failed`.

## Complete ledger and evidence

- [Complete evidence ledger](../../evidence/completion/ledger.json): **97 rows** — every one of the **58** acceptance criteria from all ten children, **17** DSC-9 checklist boxes, **6** DSC-3 architecture-boundary boxes, and **16** supplemental runtime/ownership requirements. Each row carries its source, concrete artifact/version, meaningful check, expected/actual result, named verifier and decision. Compound criteria retain the full source requirement and multiple checks; no title-only child acceptance.
- [Current source requirements and native blockers](../../evidence/completion/sources/linear-2026-10-18.json): read-only connected Linear retrieval of DSC-9, DSC-3, all ten children, and the single-case contract, with source update timestamps. Every child and DSC-9 was Backlog at retrieval.
- [Actual verification record](../../evidence/completion/verification.json), [artifact/version hash index](../../evidence/completion/artifact-index.json), and [current regression output](../../evidence/completion/checks/pytest-current.log).

**89 rows are Blocked; 1 report-composition check Fails; 7 narrowly scoped static checks Pass.** A static scope/provenance check is not child acceptance. No child or milestone is accepted from mock records, planning text, generated fixtures, probe arithmetic, passing unit tests, or this ledger's existence.

| Child | Criteria mapped | Current evidence scope |
| --- | ---: | --- |
| [DSC-24](https://linear.app/gr3enarr0w/issue/DSC-24) | 6 | Component/source evidence; genuine current runtime acceptance pending |
| [DSC-25](https://linear.app/gr3enarr0w/issue/DSC-25) | 5 | Component/source evidence; genuine current runtime acceptance pending |
| [DSC-26](https://linear.app/gr3enarr0w/issue/DSC-26) | 5 | Real isolated synthetic probe; full customer adapter acceptance absent |
| [DSC-27](https://linear.app/gr3enarr0w/issue/DSC-27) | 7 | Component/source evidence; genuine current runtime acceptance pending |
| [DSC-28](https://linear.app/gr3enarr0w/issue/DSC-28) | 8 | Component/source evidence; genuine current runtime acceptance pending |
| [DSC-29](https://linear.app/gr3enarr0w/issue/DSC-29) | 5 | Component/source evidence; genuine current runtime acceptance pending |
| [DSC-30](https://linear.app/gr3enarr0w/issue/DSC-30) | 5 | Component/source evidence; genuine current runtime acceptance pending |
| [DSC-31](https://linear.app/gr3enarr0w/issue/DSC-31) | 5 | Runbook/checklist/blank template present; actual recording absent |
| [DSC-10](https://linear.app/gr3enarr0w/issue/DSC-10) | 5 | Component/source evidence; genuine current runtime acceptance pending |
| [DSC-56](https://linear.app/gr3enarr0w/issue/DSC-56) | 7 | Fixed mock checks/checklist present; final audit explicitly Blocked |

DSC-9 itself maps completion gate 6/6, milestone-specific checks 6/6, and closure rules 5/5. DSC-3's six rows review only the MVP boundary, not its broader V1 completion.

## Verification decision and limits

The initial review refreshed from `7af5a855ea98a47d332b2428bc1325f8154eb49e` to the reviewed nightly revision after DSC-31 PR #13. That change adds only five preparation documents/template files; application source, tests, contracts and environment inputs are byte-identical. That baseline regression is retained separately. The review then incorporated DSC-56 PR #14 from current nightly; its 29 fixed acceptance tests are explicitly mock, and its final audit is Blocked. The expanded full suite was rerun at the exact merge revision recorded in verification.json.

From the isolated worktree with Python 3.13.0 and installed pytest 9.0.2:

```sh
PYTHONPATH=src python3 -m pytest tests -q
```

**Expanded current run: exit 0, 639 tests and 659 subtests passed in 33.81 seconds** at merge revision 1888d75dfc3a372b3e0b23ebc00f712b8f807706. The earlier 610-test/632-subtest baseline log remains retained separately. All seven `docs/contracts/SNAPSHOT.json` hashes match unchanged `0.1.0-draft.3`. Installed jsonschema was 4.25.1; this used the available environment, not a newly synchronized lock environment. The verification JSON records package versions and all commands. The initial bare command failed to import the src-layout package; a historical importlib workaround then omitted replenishment fixture paths. Both diagnostic logs are retained. The correct current command passes; those invocation errors are not classified as product defects.

The current regression verifies component behavior, including bounded terminal branches, independent arithmetic and immutable artifact guards. Modeling/LLM approvals, analytical inputs and reviews in those checks are explicitly mock. Existing source reconciliation reports 41 passing local fixture QA checks; this reviewer checked its retained bytes/limits and source-file hashes, not a new analytical preparation. The actual source audit must not be confused with the generated preparation test that happens to use 18,045/45 rows.

The retained [real isolated native probe](../integration/NATIVE_BOUNDARY.md) and its [saved review](../../evidence/integration/native-isolated-stage-2026-10-17/review.json) are genuine synthetic engineering evidence: Data resource use, generated/executed calculation, retrieved artifacts and filesystem/network denial controls. Its three-row result is A=5, B=5, total=10. Its saved review explicitly disclaims customer-analysis/shared-contract acceptance. Current source implements adapter wiring; older probe review text that lists wiring as future work remains historical. The unexecuted authentic customer-packet dispatch is still a current acceptance gap. Failure-run evidence has separate limits in R11 below.

## Affected work returned for authorized correction

These are concrete owner-routed correction requests in this repository review. No Linear comment, status change, reassignment or child implementation was performed. Existing native dependencies remain intact; unrelated components and V1 remain outside scope.

### R01 — Safe derived development release rejected by draft.3 validator and parent source allowlist.

Owner: **DSC-24 coordinated with DSC-3; DSC-10/26/27**. Evidence: [docs/preparation/INTERFACE.md](../../docs/preparation/INTERFACE.md).

Correction: Agree owned derived-lineage/authorization representation; adopt through owners without exposing unrestricted raw December rows.

Required recheck: Run derived partition→exact parent permission→native dispatch→retrieval; reject raw/holdout release before freeze.

### R02 — Historical information-availability evidence absent; event cutoff cannot stand in for revision timing.

Owner: **DSC-24/27 with DSC-3**. Evidence: [docs/preparation/INTERFACE.md](../../docs/preparation/INTERFACE.md).

Correction: Provide genuine knowledge-time evidence or an explicitly approved truthful representation/scope decision; do not invent a cutoff claim.

Required recheck: Reject absent/stale/unbound timing evidence; verify accepted timing against exact source and task/run.

### R03 — Current daily artifact marks completeness false; missing dates/status-return availability do not support complete daily demand horizons.

Owner: **DSC-27/28 with parent review**. Evidence: [docs/modeling/README.md](../../docs/modeling/README.md).

Correction: Investigate justified target/completeness/availability policy within approved scope and record limitations. Escalate irreducible business facts only.

Required recheck: Recheck eligible target windows, sparse/missing dates, nonpositive/status/return choices and cutoff; do not zero-fill unknowns or fabricate model performance.

### R04 — Step7 derived task/EDA/error summaries have no owner-agreed availability registration/release.

Owner: **DSC-24/3/10/28**. Evidence: [docs/parent/COORDINATION.md](../../docs/parent/COORDINATION.md).

Correction: Agree measured derived availability/lineage registration under same task; do not mutate immutable preparation or leak reserved rows.

Required recheck: Run step6→approved development-only LLM context→actual feature generation/materialization; reject future/unknown/unregistered refs.

### R05 — Genuine consent, content/chronology/independent reviewers and focused provider callbacks remain test substitutions; exact approved-packet native execution absent.

Owner: **DSC-25/10/26 and deployment/DSC-3**. Evidence: [docs/intake/README.md](../../docs/intake/README.md).

Correction: Wire authentic current consent/review/provider/configuration and genuine measured inputs through existing supported adapter.

Required recheck: Run current sign-off→same execution task→exact stage permission→native execution/adoption; reject stale input/proposal/approval and mock native dispatch.

### R06 — Recommendations stage expects quantity/report atomically; native pre-humanizer numerical approval checkpoint absent.

Owner: **DSC-10 coordinated with DSC-24/3; DSC-29/30**. Evidence: [docs/replenishment/INTEGRATION.md](../../docs/replenishment/INTEGRATION.md).

Correction: Agree same-task candidate→independent arithmetic evidence→parent approved quantity→humanizer checkpoint and bounded resume.

Required recheck: Use genuine frozen forecast/operations; reject humanizer before numerical approval; report must copy exact approved quantities.

### R07 — Native check-only verification artifact and failure-draft safe staging bridge unresolved.

Owner: **DSC-24/10/26/30**. Evidence: [docs/parent/COORDINATION.md](../../docs/parent/COORDINATION.md).

Correction: Agree owner-controlled reference/release bridge; preserve independent prior check and exact report binding.

Required recheck: Run actual check-only registration→draft verification→parent permission→delivery/readback, plus failure variant and stale-ref rejection.

### R08 — No actual preparation, step6 evaluation, live LLM features, step8 comparison/freeze, step9 pass, November30 daily forecast or final verified list/report.

Owner: **DSC-27/28/29/30/10/26**. Evidence: [docs/modeling/COMPONENT_EVIDENCE.json](../../docs/modeling/COMPONENT_EVIDENCE.json).

Correction: Collect genuine supported-host selected-case artifacts after upstream corrections, with complete versions/lineage and finite budgets.

Required recheck: Recompute real metrics under frozen rule, verify fully observed horizons and independent arithmetic/claims; keep November30 quantities invariant to December outcomes.

### R09 — Actual recording, completed index and passing final audit absent; preparation and mock audit present.

Owner: **DSC-31 then DSC-56 then DSC-9**. Evidence: [DSC-56 explicitly blocked final audit](../../evidence/acceptance/check-results.json).

Correction: Record actual successful selected-case execution; audit recording and exact artifacts, then request named final milestone acceptance.

Required recheck: Require actual successful restocking demo; terminal failure tests or helpful missing-input response cannot substitute.

### R10 — All ten current child issues remain Backlog and DSC-9 native blockers remain active.

Owner: **All child owners; DSC-9**. Evidence: [evidence/completion/sources/linear-2026-10-18.json](../../evidence/completion/sources/linear-2026-10-18.json).

Correction: Supply criterion evidence to authorized issue owners; this assignment authorizes no issue-status changes.

Required recheck: Refresh current Linear requirements/blockers and final accepted ledger before any downstream milestone advance.

### R11 — Retained native failure evidence has narrower limits than complete failure-path acceptance.

Owner: **DSC-26**. Evidence: [evidence/integration/native-failures-2026-10-17/review.json](../../evidence/integration/native-failures-2026-10-17/review.json).

Correction: After classifier correction, collect relevant actual rechecks; identify timeout process-exit uncertainty, pre-command cancellation and unexercised account quota distinctly.

Required recheck: Do not count offline invalid-code replay as real corrected execution, declared zero budget as account exhaustion, or cancellation before command as mid-compute termination.


### R12 — Report composition produces colliding source-local finding identities

Owner: **DSC-29 with DSC-24/3; DSC-30 enforces the agreed rule**. [DSC-56 reproduced discrepancy](../acceptance/REVIEW.md#reproduced-finding-identity-discrepancy) passes unchanged shared findings through the real producer and independent verifier: **18 declarations, 15 unique identities**. The verifier correctly blocks delivery. This is a concrete component interoperability defect on mock inputs, not a real customer/model failure.

Correction: agree source-qualified IDs or namespace at composition while preserving immutable source/evidence references. Rewritten positive mock findings are not a fix. Recheck source findings → report composition → independent identity/claim/narrative checks → exact draft approval/delivery; preserve unaffected model/quantity evidence. No affected owner files were edited here.

## Final acceptance requirements

After affected owners provide authorized corrections, refresh against current nightly and current Linear requirements. Remeasure artifacts and source bindings; invalidate every dependent stale approval. Rerun each failed/affected component check and relevant integrations within the declared retry/time/compute budgets, then record new actual results and named verifier decisions.

The successful acceptance packet must contain actual read-only intake/current sign-off; the same approved execution task; supported native Codex/Data invocation and safe stage release; genuine preparation/lineage and justified targets; step6 initial-model/baseline gate; actual step7 LLM definitions and validated materialization; step8 bounded comparison/frozen model/features/preprocessing/rule and separate November30 forecast; step9 fully observed unseen evaluation under the predeclared rule; independently reconciled orders; and one verified delivered final report/readback. That report must contain the list, measured model results, concise customer-relevant EDA/feature findings and material synthetic/data limitations. Routine analytical progress remains internal; material business facts and real blockers receive targeted handling.

Review stock/receipt arithmetic independently: lead time plus review protection period, safety stock, usable stock, timely arrivals, no summary/ledger double count, zero clamp, positive-order minimums/multiples and earlier-shortage exceptions. Verify Product_ID/Store_ID, reliable names, product_unit, November30 date and all excluded/unresolved keys. Unknown missing sales dates are not zero. Inventory_Level and Delivery_Days cannot replace operational snapshot/supplier lead time. December outcomes cannot alter the November30 model choice, fit, inputs or quantities.

Failure branches require parent source/split/model/metric/runtime review, bounded authorized defect correction and affected rechecks with the frozen choice/rule unchanged. Confirmed underperformance, unsuccessful correction or unresolved/exhausted execution ends with a verified truthful explanation, no quantities, runner-up, holdout tuning or indefinite review. Explain this MVP's supplied-data/scope limitation; do not assert universal impossibility or fabricate measured failure. Passing those branch checks is distinct from successful model validation and the required successful recorded restocking run.

Require the actual DSC-31 successful recording and matching artifact/version index, then DSC-56's fixed final audit, then an explicit named final milestone acceptance decision. Preserve DSC-9's native downstream blockers until that decision and current passing evidence agree. This assignment supplies no issue-status authority.

## Remaining limitations and ownership

The sole DSC-9 write areas are `docs/completion/` and `evidence/completion/`, as already allocated by [DSC-3](../architecture/OWNERSHIP.md). This follows the published owner agreement; no fresh architecture-owner acknowledgment is invented. Shared schema/release changes go through DSC-24 coordinated with DSC-3; parent changes through DSC-10. This review creates no platform, runtime, component patches, app, extra dataset suite or DSCraft interface change.

Drive and Miro were not opened remotely in this review; their linked references and local provenance metadata are available, but current remote byte identity/board contents are not claimed. The current Linear issues and contract were read through the connected tool. Source hashes do not establish origin/license, historical knowledge timing or ledger completeness. Missing-data guidance works locally even though the shared report envelope has no genuine preexecution binding; do not fabricate execution to fit it. Process-restart restoration is unsupported; existing in-process review/event evidence must not be deserialized as authority. Record that limit without making a new runtime a DSC-9 deliverable.

**Final named review decision: Blocked.** Branch/PR/nightly consolidation publishes this review only; it does not waive missing evidence, accept a failed model run, close issues or release downstream milestones.
