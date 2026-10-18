# DSC-30 component validation evidence

Observed October 18, 2026 UTC (October 17 local), Python 3.13.0 and jsonschema 4.25.1, on the isolated `codex/dsc-30-independent-verifier` branch. The component started from `nightly` `83f134f`; shared contract version remains `0.1.0-draft.3`.

| Executed check | Observed result | Scope |
| --- | --- | --- |
| `PYTHONPATH=src python3 -m pytest tests/verification -q` | 124 passed, 19 subtests passed | Independent arithmetic, evidence-linked claim/guidance review, current approvals, terminal outcomes and exact delivery readback |
| `PYTHONPATH=src python3 -m pytest tests -q` | 342 passed, 237 subtests passed | Complete repository regression suite before consolidation |
| Recomputed SHA-256 for every entry in `docs/contracts/SNAPSHOT.json` | All seven matched | Shared schema, validator and examples unchanged |
| `git diff --cached --check` | Passed | Staged owned paths have no whitespace errors |

After independent review added null-name compatibility and repeated/concurrent delivery protection, the branch merged the newer `nightly` `0e0d178` (DSC-25) without conflicts. The combined final regression command `PYTHONPATH=src python3 -m pytest tests -q` passed **376 tests and 250 subtests**. This includes 129 verification tests. Duplicate successful, mismatched-readback, interrupted and concurrent delivery attempts invoke the publisher at most once per approval.

Before PR consolidation, `nightly` advanced again to `ee16115`, including DSC-27 preparation and DSC-10 parent guards. These changes merged without conflicts; the same complete test command then passed **458 tests and 304 subtests**. Shared contract files remain unchanged. This combined regression establishes component compatibility, not a genuine analytical customer run.

The DSC-29 failure-lineage follow-up started from `1418220` and then incorporated parent-release `nightly` `a52a310`. Its lifecycle suite passed **86 tests**, including the actual producer-shaped terminal handoff and ten rejection variants. The complete repository run passed **549 tests and 361 subtests**, including 140 verification tests, with:

```sh
PYTHONPATH=src:tests/parent:tests/preparation python3 -m pytest tests --import-mode=importlib -q
```

That exact invocation was needed at `a52a310`: ordinary collection encountered upstream duplicate `test_features.py` basenames in preparation/modeling, while importlib collection alone omitted the preexisting top-level parent/preparation fixture-helper paths. No tests were excluded and no shared configuration was changed. The affected owners were notified; DSC-28 is correcting its filename independently. All seven agreed contract hashes still match.

The independently expected arithmetic examples include demand `10` plus safety `2`, minus usable stock `5` and eligible receipts `2`: clamped need `5`, minimum `5` and multiple `4` yield `8`. Stock sufficient to eliminate the shortage yields zero without triggering the minimum. Fractional forecasts retain exact Decimal arithmetic. Earlier shortages are withheld even when a later receipt would make total-horizon net arithmetic look sufficient.

Other executed counterexamples include changed quantity intermediates despite producer pass flags; duplicated incoming-order lines; absent daily forecasts; stale stock or future information; incompatible units; conflicting names; unsupported synthetic provenance; changed manifest dates/counts/hashes; stale report versions; pending terminal parent reviews; fabricated measured failure; altered customer text; parent veto; and output bytes that differ from the approved draft. Faithfully reported per-key exceptions are preserved alongside supported rows. Success and rejected readback checks persist typed evidence bound to the exact approved verification reference.

These are **component tests with explicitly mock analytical runs and engineering samples**. They establish that the checks executed and caught their named counterexamples. They do not establish real forecast performance, a genuine completed customer run, current real model/quantity approval, supported end-to-end analytical execution or customer delivery. Those acceptance waits remain recorded in [README.md](README.md).
