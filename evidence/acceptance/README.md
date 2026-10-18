# DSC-56 observed engineering results

Reviewer: **Codex / DSC-56 fixed-MVP verification engineer**, October 18, 2026.
Source commit: `412520f4c1ba959330a79ab93b95354778e0d2cd`, refreshed from
nightly `93f6cc9f7725ae0d9d5442bd64491c007f4d372c`.

[check-results.json](check-results.json) records **29 passing checks and 27
passing subtests**, 5.98 seconds. All analytical execution, customer/LLM/host
responses and approvals are MOCK. Actual component code and assertions ran.
The complete repository regression passed **639 tests and 659 subtests** in
34.07 seconds; the subsequent nightly refresh added only DSC-31 documentation
and templates. All seven hashes in the unchanged DSC-24 snapshot matched.

The check report binds 132 source/test/example/document files by SHA-256,
including imported component helpers, contract examples and the snapshot index.
Its exact commands, Python/pytest/jsonschema versions, expected/actual outcomes
and per-check decisions are retained. No report grants genuine acceptance.

[affected-stale-recheck.json](affected-stale-recheck.json) is a recorder selector
smoke check: **one stale-candidate test passed; 28 other checks are `not_run`**.
It proves affected-only recording does not reuse older passing results. No
production defect correction or new model score is implied by that invocation.

[The 58-criterion ledger](../../docs/acceptance/checklist.json) keeps every
criterion's final acceptance decision blocked. The tests reproduce and block
source-local finding-ID collisions after report composition; the concrete
owner correction request is in [the review](../../docs/acceptance/REVIEW.md).
The report's final audit also remains blocked pending real coherent execution
artifacts, current DSC-24/10 evidence and the actual DSC-31 recording. The new
DSC-31 preparation/template files contain no captured demonstration.

Recheck failed/affected consumers under the [review matrix](../../docs/acceptance/REVIEW.md#affected-rechecks-after-correction),
preserving unaffected evidence and frozen model/feature/rule/chronology. Do not
close DSC-56/9 or call failure handling a successful restocking demonstration.
