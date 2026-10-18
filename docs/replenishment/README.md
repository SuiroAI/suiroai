# DSC-29 replenishment consumer

This component implements candidate arithmetic for the single historical retail
case. It does not train/select a model, approve quantities, humanize candidates,
advance a checkpoint, or authorize delivery. The source baseline is `nightly`
commit `83f134fb7674de64d7f3a6b62f984bb6486ec81d`. The agreed shared interface is
DSC-24 `0.1.0-draft.3`; no shared files or dependencies are changed.

Write ownership is confined to `src/suiroai/replenishment/`,
`tests/replenishment/`, `docs/replenishment/`, and the separately owned reporting
counterparts allocated to DSC-29 in
[the architecture map](../architecture/OWNERSHIP.md). DSCraft and source datasets
remain unchanged.

## Calling boundary

`Handoff(records, external_refs, read_bytes, parent_confirms, allow_mock=False)`
validates the closed current contract graph. `read_bytes(ref)` is trusted
application artifact access; the consumer checks the exact SHA-256 on every
read. `parent_confirms(record_ref, decision)` is the trusted DSC-10 ledger
lookup, required to return literal `True` for the exact record and decision.
Neither callback may come from model-generated code or a submitted packet.
Graph validation alone cannot authenticate a checker or prove execution.

`calculate_candidate(handoff, artifact_id=..., scope_ref=...,
scope_reader=..., forecast_reader=..., source_namespace=...)` returns a
DSC-24 `quantity_result`. The consumer checks passed final validation, the exact
frozen forecast binding, permitted arithmetic action, and authenticated parent
final-validation permission before reading arithmetic inputs. Failed or
unreviewed validation cannot construct real orders. Mock handoffs require
explicit `allow_mock=True` and retain mock provenance throughout.

The application supplies two format adapters. These are internal Python
boundaries, **not new shared serialized schemas**:

- `scope_reader(verified_bytes)` returns explicit requested keys with
  `source_namespace`, `product_id`, and `store_id`. Its immutable reference must
  be an approved source or frozen development input; an inner join is never a
  substitute for scope. Missing forecast/stock/policy keys remain visible.
- `forecast_reader(verified_bytes)` returns daily dictionaries with `key`,
  `date`, `quantity`, `quantity_unit`, `as_of_date`, and
  `latest_information_available_date`. Quantities are finite/nonnegative, unit
  is `product_unit`, as-of is November 30, and information availability is no
  later than that date. Every day of each lead-plus-review horizon must be
  present exactly once. Additional forecast dates are allowed but not included
  in that key's requirement. Aggregate horizons cannot be split uniformly or
  silently extrapolated. DSC-28 supplies genuine frozen daily predictions.

Stock, receipt, and policy file references resolve through the actual approved
submission roles and namespace, not ambient paths. CSV headers match the active
source files, including `Open_Order_Ledger_Complete`. Stock snapshots and policy
effective dates must equal review date in this deliberately bounded consumer;
older policy/snapshot inputs need a separately reviewed effectivity/movement
adapter. Every operational row must declare synthetic provenance, and the
execution contract must explicitly classify those sources as synthetic.

Product names are omitted by the numerical consumer because no independently
bound name-mapping adapter is supplied. IDs remain exact. No name is inferred.

## Arithmetic and dated coverage

For each requested key, the inclusive horizon is December 1 through review date
plus supplier calendar lead days plus review calendar days:

`need = max(0, sum(daily_forecast) + safety - usable_stock - eligible_receipts)`

For positive need, `order = ceil(max(need, minimum) / multiple) * multiple`.
Zero need yields zero even when a minimum is declared. Decimal arithmetic
retains exact values in producer evidence. Quantities not representable in the
shared JSON numeric fields are rejected rather than silently rounded.

All open receipt lines, including those beyond the protection horizon, must
sum exactly to `On_Order_Qty`. The summary is only a reconciliation total; it
is never subtracted a second time. Future order dates, overdue receipts,
duplicate line IDs, invalid dates, negative quantities, incompatible units,
unknown completeness, and sum discrepancies become explicit exceptions.
Missing ledger keys mean zero **only** with the approved complete-synthetic-ledger
policy and the key's complete-ledger assertion; this never zero-fills demand.

Only receipts due inside the horizon reduce aggregate need. Date-only receipts
and the candidate order's lead-date arrival receive conservative end-of-day
treatment: each day's forecast demand must be coverable before that day's
receipts/order arrive. A negative before-arrival balance with a nonnegative
after-arrival balance is `timing_ambiguity`; a remaining negative balance is
`shortage`. Both withhold the key's order. This conservative check asserts no
unsupported within-day availability convention and never credits a later
receipt against earlier demand. A reviewed/source-backed intraday convention
would require coordinated consumer/verifier changes, not a silent override.

Other keys continue with explicit exceptions. A malformed/unattributable file
or missing entire source is a component input error for parent handling, not a
zero list or measured validation failure. The union of scope and all source
keys prevents silently dropping unexpected/mismatched keys.

## Evidence and approval handoff

Candidate rows retain inputs, units, exact horizon, frozen references,
unrounded need, minimum/multiple, and rounded order. Approval fields are null;
independent-check references and parent decisions are empty. Each per-key
`arithmetic_checks[].actual` contains JSON audit detail: original CSV row
positions, exact decimal totals, receipt line IDs/dates/eligibility, signed
need, daily stock balances, candidate arrival, and the explicit reason where
timing fails. All checks are labeled producer self-checks, never independent
verification. Numeric input errors retain the immutable input references and
attributable row positions even when no arithmetic can be computed.

DSC-30 independently reads the same bound input bytes and recomputes expected
quantities. DSC-10 supplies authenticated approval, creating a later immutable
quantity version referencing the checked candidate, preserving rows/exceptions
and populating approved quantities. This module does not implement approval.
The [reporting consumer](../reporting/README.md) reads that approved artifact.
Neither component sends interim analytical progress or delivers a report.

## Validation and remaining integration work

Run from the application worktree with the existing locked environment:

```sh
PYTHONPATH=src /Users/ceverson/Development/SuiroAI/suiroai/.venv/bin/python -m unittest discover -s tests/replenishment -p 'test_*.py'
```

The [independently calculated examples](NUMERICAL_EXAMPLES.md) and component
tests use explicit mock inputs. They demonstrate consumer behavior, not actual
model validation, genuine forecasts, the 336-key recommendation, or MVP closure.
Real integration still requires the actual approved execution graph, genuine
frozen daily forecast/scope adapters, source artifacts, authenticated parent
ledger decisions, DSC-30 numerical/claim checks, and final parent authorization.
Missing daily predictions is a real input gap, never permission to manufacture
a profile. Synthetic inventory/policy keeps any resulting advice illustrative.

[MOCK_CANDIDATE.json](MOCK_CANDIDATE.json) is the reproducible public-consumer
output from `tests/replenishment/test_handoff.py`'s `scenario()`/`calculate()`.
It includes intermediate daily balances and input/evidence bindings. It is an
unapproved mock artifact, separate from the reporting examples' input graph.
