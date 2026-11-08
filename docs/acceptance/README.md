# DSC-56 fixed retail verification

Named engineering reviewer: **Codex / DSC-56 fixed-MVP verification engineer**.
Source of truth: `nightly`, initially at
`7af5a855ea98a47d332b2428bc1325f8154eb49e`, refreshed to
`93f6cc9f7725ae0d9d5442bd64491c007f4d372c` before publication.
The architecture owner's [published allocation](../architecture/OWNERSHIP.md)
reserves these acceptance tests, documents and evidence. The agreed shared
interface is DSC-24 `0.1.0-draft.3`; no shared contracts or runtime are changed.

[requirements.json](requirements.json) captures every acceptance criterion from
DSC-24/25/26/27/28/29/30/31/10/56: **58 criteria**, read through connected Linear
on October 18, 2026. Each issue URL and last-updated timestamp is retained.
The linked [single-case contract](https://linear.app/gr3enarr0w/document/retail-mvp-single-restocking-case-shared-data-and-implementation-72e8278521db)
and DSC-3/9 were also read. These sources are requirements, not implementation
evidence. No issue or milestone status is changed.

[checklist.json](checklist.json) binds each criterion to its expected behavior,
source version, implementation/check groups, actual evidence location,
reviewer decision and uncovered proof. [check-results.json](../../evidence/acceptance/check-results.json)
records each executed check's expected/actual result, exact test ID, named
reviewer, code commit, current source SHA-256 bindings and environment. The code
commit identifies the checkout; the measured file hashes also bind uncommitted
acceptance files at recording time. This local worksheet is not a replacement
for DSC-24's runtime evidence-record schema.

The tests exercise actual component code at intake/parent/adapter,
preparation/modeling and quantity/report/independent-verifier seams. Customers,
consent, host execution, analytical outcomes and LLM responses are explicitly
**MOCK**. Small generated examples are deliberately not the real supplied data.
No native customer analysis or recording is performed by these checks.

From the application checkout, with Python having the existing development
packages `pytest` and `jsonschema` available:

```sh
PYTHONPATH=src python3 docs/acceptance/record_checks.py \
  --reviewer 'Codex / DSC-56 fixed-MVP verification engineer'
```

The recorder collects and runs only `tests/acceptance/`. It checks source bytes
before and after execution, records skips/missing results as blocked, and exits
nonzero on failed checks or evidence recording. Its successful exit means only
that the selected engineering checks passed. Final audit always remains blocked
for manual evidence review. It never authorizes a model, customer output or gate
closure. The standard full regression command remains:

```sh
PYTHONPATH=src python3 -m pytest -q
```

The unmodified baseline passed 610 tests and 632 subtests in 33.03 seconds in
this session. That historical baseline is separate from the acceptance check
record and is not a claim about current real demand/model accuracy.
The complete suite with these checks passed **639 tests and 659 subtests** in
34.07 seconds. The subsequent nightly refresh added only DSC-31 preparation
documents/templates; they explicitly contain no recording or completed run.

After a correction, identify changed artifact versions and use the
[affected-dependency matrix](REVIEW.md#affected-rechecks-after-correction).
Run only failed checks and affected consumers, saving a new report so the
original evidence remains available. For example, a narrative/claim correction:

```sh
PYTHONPATH=src python3 docs/acceptance/record_checks.py \
  --reviewer 'Codex / DSC-56 fixed-MVP verification engineer' \
  --only tests/acceptance/test_data_output_acceptance.py::test_mock_generated_report_false_measured_claims_block_delivery \
  --output evidence/acceptance/affected-claims-recheck.json
```

Omitted checks are recorded as `not_run`; older successes are never silently
merged into the new report. Compare the old/new source bindings and invalidate
dependent approvals. A changed contract, mock helper, test or implementation
hash makes affected evidence stale. Refresh current Linear criteria before a
final audit; the captured timestamps do not prove requirements are still current.

**Final acceptance: blocked.** All 58 rows retain their uncovered genuine proof.
Require actual coherent task/run/input/proposal-bound artifacts, real approved
Codex/Data execution, measured comparable models and actual LLM features,
unchanged November 30 forecast and frozen acceptance rule, untouched fully
observed holdout, independently verified arithmetic/claims and customer delivery,
the DSC-31 recording, and current DSC-24/10 contract/guardrail review. A named
reviewer must inspect them and record decisions. Isolated synthetic native Data
evidence already exists in the integration subtree; it has a narrower scope.

[REVIEW.md](REVIEW.md) records concrete discrepancies, owner requests and
uncovered criteria. Truthful missing-input behavior and correct terminal failure
handling establish those branches only. They do not prove a successful restocking
demonstration. No second-best model, holdout tuning, invented operational facts,
universal-impossibility claim or silent waiver is permitted.
