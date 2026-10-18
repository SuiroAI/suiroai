# DSC-29 numerical verification examples

These are **MOCK DEVELOPMENT EXAMPLES**, independently calculated by hand to
exercise the consumer. They are not forecasts for supplied sales, successful
model validation, parent approval, DSC-30 independent output verification, or
authorization to send a report. All operational quantities in these examples
are declared synthetic and use `product_unit`.

The review date is November 30, 2025. Supplier lead time is two calendar days;
the review period is two calendar days. The protected demand dates are December
1–4 inclusive. A new order arrives on December 2 under conservative end-of-day
timing. Every day must remain nonnegative **before** date-only receipts and the
new order arrive. A same-day delivery that would erase a negative balance
leaves a timing-ambiguity exception; a later delivery leaves a shortage
exception. Neither is a valid order row.

For eligible ledger receipts `R`, forecast requirement `F`, declared safety
stock `S` and usable stock `U`, the independent calculation is
`need = max(0, F + S - U - R)`. If need is positive, raise it to the declared
minimum, then round upward to a multiple. A zero need stays zero.
`On_Order_Qty` must equal the complete ledger total, including deliveries beyond
the horizon, and is never subtracted separately.

| Mock example | Daily forecast, Dec 1–4 | Usable stock | Safety | Receipts | Positive minimum / multiple | Independent result |
| --- | --- | --- | --- | --- | --- | --- |
| Zero need | 1, 1, 4, 4 | 20 | 2 | none | 100 / 12 | Signed need `10+2-20=-8`; net need 0; order 0. |
| Minimum and multiple | 0.5, 0.5, 1, 2 | 3 | 0 | none | 7 / 5 | Need `4-3=1`; minimum raises to 7; next multiple is 10. |
| Exact decimal boundary | 0.1, 0.2, 1.1, 1.6 | 1 | 0 | none | 1 / 1 | Exact forecast 3.0; need 2.0; order 2. |
| Summary double-count trap | 1, 1, 4, 4 | 4 | 2 | 3 on Dec 2; summary 3 | 1 / 1 | Need `10+2-4-3=5`; order 5. Subtracting summary again would incorrectly give 2. |
| Receipt beyond protection horizon | 1, 1, 4, 4 | 4 | 2 | 3 on Dec 5; summary 3 | 1 / 1 | Eligible receipts 0; need `10+2-4=8`; order 8. Ledger total still reconciles to summary 3. |
| Later receipt cannot cure shortage | 2, 4, 1, 1 | 3 | 0 | 8 on Dec 4; summary 8 | 1 / 1 | Aggregate signed need `8-3-8=-3` and candidate 0; Dec 1 closes at 1, Dec 2 closes at -3. Withhold as shortage. |
| Same-day timing unresolved | 2, 4, 1, 1 | 3 | 0 | 8 on Dec 2; summary 8 | 1 / 1 | Dec 2 balance before arrival -3 and after arrival 5. Withhold as timing ambiguity. |
| Order too late | 4, 1, 1, 1 | 3 | 0 | none | 1 / 1 | Aggregate need 4, but Dec 1 before-arrival balance is -1; the Dec 2 order cannot cure it. Withhold. |

For the summary example, daily balances are independently `4-1=3`, then
`3-1+3+5=10`, then `10-4=6`, then `6-4=2`, exactly the declared safety stock.
The Dec 2 balance before arrivals is 2, so the date-only convention is satisfied.

An additional precision example uses forecasts `0.1, 0.2, 1.1,
1.6000000000000001`. Exact requirement is `3.0000000000000001`, need is
`2.0000000000000001`, and mathematically upward rounding would require 3.
The shared JSON numeric contract cannot preserve these inputs faithfully;
the consumer withholds this key rather than silently converting its need to 2.

The exact-arithmetic support bound is also explicit: daily forecasts `1e-29,
0,1,1`, stock 2 and safety 0 mathematically leave need `1e-29`; computation
withholds this key with `forecast_precision_exceeds_exact_arithmetic_support`
rather than reporting zero. For representable demand `0,0,0,6.000000000000001`,
stock/safety 0 and multiple 3, three packs are required: order 9, with final
balance `2.999999999999999`. That expected result remains unchanged when the
caller's ambient Decimal precision is only 2. A policy lead time of `10**33`
days becomes an explicit `policy_horizon_outside_supported_calendar` exception
instead of an uncaught date overflow. Public-API regressions check both the
excess-precision and calendar-bound exceptions produce no order row.

## Coverage and gap examples

The suite repeats a zero-receipt case for 210 distinct mock product/store keys.
With forecasts `1,1,4,4`, stock 4, safety 2, no ledger lines, summary 0, and an
approved complete-synthetic-ledger assertion, each key has need/order 8. For
each same key, changing completeness to false produces an explicit exception.
The count 210 mirrors the stated operational scenario only; these keys and
tests do not certify the genuine ledger.

Missing or duplicate stock/policy rows, partial or duplicate daily forecasts,
stale/future operational dates, wrong units, future forecast availability,
wrong forecast origin, synthetic-provenance mismatches, nonfinite/negative
values, invalid order policy quantities and unreconciled receipt summaries
are rejected. Duplicate receipt identifiers withhold every affected key. A
requested key missing stock remains an exception rather than disappearing in
an inner join. Namespace mismatch cannot silently join unrelated records.

## Evidence bindings and verification

`tests/replenishment/test_calculation.py` supplies normalized synthetic rows
and literal independent expected quantities. `test_handoff.py` exercises the
public `calculate_candidate` consumer using the existing DSC-24 draft.3 mock
record graph and test-specific CSV/forecast/scope bytes. A freshly constructed
mock task approval binds those bytes; record references, source hashes, source
sizes, submission input digest, proposal digest and frozen manifest are
consistent within that fixture.

The public tests require passed final validation and authentication of the
exact parent review before any source read. Altered source bytes, an incorrect
saved-forecast reference and implicit mock opt-in are rejected. A failed final
validation constructs no candidate and reads no operational sources.

Each successful candidate carries the exact frozen forecast reference, final
validation reference, arithmetic source references, bound scope and source row
positions. The late-receipt exception test checks its retained signed need,
receipt quantity/date, source row and daily shortage trace. Producer
`arithmetic_checks` remain self-checks: the tests do not claim they are
independent runtime verification. Candidates have no approved quantities,
parent decision or independent check references.

Run the mock regression examples from this worktree:

```sh
PYTHONPATH=src /Users/ceverson/Development/SuiroAI/suiroai/.venv/bin/python -m unittest discover -s tests/replenishment -v
```

Genuine integration remains blocked until the parent supplies a genuine passed
validation result, immutable frozen daily trajectory and explicitly bound
scope/source artifacts. Numerical parent approval and independent DSC-30
verification must precede report delivery.
