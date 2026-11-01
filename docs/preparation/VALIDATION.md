# DSC-27 implementation evidence and remaining acceptance

All component fixtures and approvals in `tests/preparation/` are explicitly
MOCK. Tests calculate actual results on generated CSV bytes and do not claim
real source analysis, customer authorization, model fitness or issue closure.

Run from the application checkout:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests/preparation -v
```

On October 17, 2026, 37 preparation tests passed (0.622 seconds), along with
all 77 unchanged contract tests (1.389 seconds) and all 141 unchanged integration
tests (6.515 seconds). These 255 checks are engineering verification. No native
customer Data invocation or supplied-fixture analytical preparation ran.

| Requirement | Implementation/check | Evidence limit |
| --- | --- | --- |
| Raw counts, exact duplicates, shared orders | Generated 18,045-record/45-duplicate case independently counts rows, distinct identities, partition totals and source byte hash; a separate shared-order/cosmetic case verifies exact identity before normalization | Generated mock count coincidence is explicitly not actual supplied-fixture reconciliation |
| Nonpositive quantity and status/returns | Actual generated status mix, malformed quantity rejection, quarantine, retained/excluded source membership, gross-unit and alternative totals | Real fixture's eight nonpositive rows are not claimed to have been investigated during this implementation run |
| Safe temporal boundaries | Poison December values leave every development value unchanged; future rows, raw release and future predictors reject | Approved physical release/controller/native path still requires genuine execution |
| Joins and operational meaning | Duplicate keys, missing coverage, units, dates, PO identity, supplier timing, summary double counting and noncomplete ledgers reject; multiple due-dated lines align once | Synthetic mock operational arithmetic is not acceptance of actual inputs |
| Sparse dates and grain | Observed dates retained; missing dates omitted; repeated daily keys reject; incomplete/missing horizons unavailable despite global presence | No source-completeness fact is manufactured |
| Initial feature timing and folds | Calendar values recomputed, unapproved fields reject, training fold excludes validation labels, unseen IDs remain unknown, vocabulary frozen | No model metric/LLM generated feature contribution is claimed |
| Typed result and adapter boundary | Actual hashed JSON artifacts, raw hash lineage, reserved receipt binding, shared-schema/handoff validation, mocked adapter retrieval and trusted candidate review | Mock callbacks are not a real parent authorization or supported customer run |

The actual raw-to-derived release regression rejects before native dispatch
under the pinned shared validator. The retrieval test uses an explicitly
artificial MOCK sixth approved source, solely to verify serialization/retrieval
and trusted candidate review. This is not a production release workaround.
See the [current release blocker](INTERFACE.md#current-shared-release-blocker).
Real result serialization separately rejects unknown retrospective information
availability instead of substituting an event cutoff for a source timing fact.

Review exposed and corrected an omitted `Returned` status and a receipt-key
counter inflated by dictionary access to empty receipt groups. Regressions
preserve the returned-status target decision and explicit zero-open-order keys.
Read-only review also requested measured reserved partition bindings, explicit
unknown source revision timing, and accurate identifier feature descriptions;
the implementation and interface documentation retain these controls.
The final review also reproduced a dropped operational-output row that left a
stale passing summary; independent result reconciliation and five mutation
regressions now reject removed/duplicate operations, changed receipt totals,
missing operational lineage and wrong as-of context.

The actual source dictionary and manifest were inspected; their declared
18,045/45/18,000 counts, 336-key operational scope and source hashes remain
**supplied fixture expectations**. Real preparation must independently remeasure
them from the immutable source under the approved supported path. The full raw
audit is deliberately outside development/feature-generation context.

Production acceptance still waits for genuine DSC-25 sign-off/current versions,
DSC-10 parent permission/release review, and the DSC-26 supported invocation with
separate controller/dev/reserved artifacts and reviewed candidate evidence. A
working mock consumer does not satisfy these waits. DSC-28 must assess whether
the incomplete daily observations can support the approved forecast scope; no
second task or purportedly reliable restocking list is created here. Findings
and limitations remain evidence-linked in the preparation result for the final
report, with no runtime customer analysis-progress output.
