# DSC-29 completed component checks

Source baseline incorporated for final validation: `nightly`
`f1a60b12622179a6fc2e9aa0656c3a387ba78096`. Checks ran from the DSC-29 worktree
without changing shared contracts, manifests, the lockfile, or source data.

```sh
PYTHONPATH=src /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest tests -q
```

**Observed result: 610 tests and 632 subtests passed in 25.90 seconds.** This
includes 41 replenishment and 20 reporting tests, plus the existing nightly
suites. The existing global test environment provides Python 3.13, pytest 9.0.2
and jsonschema 4.25.1; no dependency was installed or added to the application.

Two producer-to-verifier checks run the actual independent DSC-30 arithmetic
module against the produced mock candidate and a withheld late-receipt case.
The checker agrees on the candidate quantity and separately discovers the
timing shortage. It does not call producer arithmetic to derive its expected
result. These checks remain mocked integration examples, not a real parent
approval or customer-delivery verification.

The seven DSC-24 pinned snapshot file hashes matched
`docs/contracts/SNAPSHOT.json`. Candidate and success/failure mock JSON records
passed shared record validation; the preexecution missing-input example is
explicitly local guidance. `git diff --check` and Python compilation passed.
Changes are limited to the six reserved DSC-29 directories.

Review exposed and corrected silent Decimal precision loss, calendar overflow,
the report action gate, zero-quantity receipt acceptance, and conflicting
product names across stores. Regression coverage retains those cases and
immutable input/parent permission checks.

The [integration ledger](INTEGRATION.md) lists genuine upstream evidence,
numerical parent checkpoint/resume, and final-verification/delivery waits.
Passing these tests does not clear those acceptance gates or close DSC-29.
