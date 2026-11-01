# DSC-29 integration and evidence bindings

This is component implementation evidence, not a successful retail run or
customer-delivery authorization. The source branch began at `nightly` `83f134f`
and incorporated `f1a60b1` (including DSC-27/28/30 and the parent) before final
verification. All new writes remain inside the six DSC-29-owned directories.
The DSC-24 schema/validator and source datasets are unchanged.

## Requirement-to-artifact map

| Requirement | Implementation and inspectable evidence |
| --- | --- |
| Passed validation precedes candidate construction | `Handoff` validates the exact closed graph; `calculate_candidate` requires passed final validation and authenticates its parent decision before any source read. `test_handoff.py` tests the rejected failure/unauthenticated paths. |
| As-of arithmetic with no receipt double count | `calculation.py` binds approved file roles, exact source hashes, scope, frozen forecast, dates and units; its per-key JSON trace preserves input row positions, receipts, daily balances, exact decimal sums and rounding. `NUMERICAL_EXAMPLES.md` independently calculates expected values. |
| Timing, incomplete and mismatched inputs | Public mock tests retain missing and unexpected keys and withhold late/same-day-shortage quantities; no inner join or blanket zero filling is used. Precision and date-overflow cases produce exceptions. |
| Optional verified display names before approval | An explicit immutable name mapping is applied to candidates before checking and approval. Invalid/missing mappings in a requested name adapter become per-key exceptions. Reports never enrich or rewrite approved rows. |
| Independent numerical evidence before humanizing | `draft_success` requires the exact later approved quantity version, earlier candidate, accepted independent typed evidence and trusted parent confirmation. Humanizer invocation is rejected first if any prerequisite or permitted action is missing. |
| Evidence-backed one-report draft | `reporting/drafts.py` copies approved rows/exceptions and verified findings; baseline/candidate/unseen scores and limitations are bound to the exact originating artifacts. Claims are immutable sentences; the focused humanizer can reorder claim IDs only. |
| Separate failure/capability variants | `MOCK_DRAFTS.json` retains distinct success, missing-input, measured failure and execution failure outcomes. Failures have no quantity list; capability guidance never invents execution/approval. |
| No final delivery authority | Neither consumer exposes a publisher, stage transition or delivery permission. DSC-30 checks the finished draft and DSC-10 authorizes its exact response. |

The numerical mock output is in [MOCK_CANDIDATE.json](MOCK_CANDIDATE.json).
The report/failure mock outputs are in
[MOCK_DRAFTS.json](../reporting/MOCK_DRAFTS.json). These are separate explicitly
mock input chains. The report example consumes the DSC-24 example's mock
numerical approval; it does not approve the numerical example produced here.

## Actual owner coordination

The published [ownership map](../architecture/OWNERSHIP.md) reserves the exact
paths used here. A fresh acknowledgment request was sent to the actual DSC-3
and DSC-24 sessions; no fresh response is invented. The previously agreed
draft.3 snapshot is the development contract. No new shared schema, dependency,
parent implementation or infrastructure is introduced.

DSC-28 and DSC-30 explicitly acknowledged the daily adapter fields `key`,
`date`, `quantity`, `quantity_unit`, `as_of_date` and
`latest_information_available_date`, complete daily coverage, immutable scope
keys, and no aggregate interpolation. DSC-28's
`modeling.prepared.forecast_daily_rows(bytes)` and `scope_keys(bytes)` implement
that agreed format; its scope reference belongs in frozen development inputs.
DSC-30 independently reads the operational CSVs and recomputes arithmetic;
it does not import the replenishment calculation. Conservative date-only
arrival treatment was agreed. Optional names must bind before numerical
approval; no report-time name enrichment changes approved rows.

## Genuine integration blockers

1. **Numerical parent checkpoint before report resume.** The current parent
   recommendations stage expects quantity and report artifacts in one atomic
   adapter candidate. The actual DSC-10 owner confirmed it lacks a native
   pre-humanizer numerical registration/resume checkpoint. Genuine execution
   therefore cannot yet run candidate calculation → independent DSC-30 evidence
   → actual parent approval → humanizing within that stage representation.
   DSC-10/24/3 must agree that same-task handoff. These consumers deliberately
   reject fabricated embedded authority; mock approval is not a workaround.
2. **Genuine upstream data/model evidence.** Real recommendation construction
   still requires justified preparation/target/completeness treatment, actual
   required LLM feature evidence, a frozen daily forecast and explicit scope,
   passed reserved validation, and authenticated current approvals. Current
   incomplete daily source evidence is not transformed into invented observed
   zeros or uniformly allocated forecasts. All operational advice is synthetic.
3. **Independent finished-draft verification.** DSC-30 must validate genuine
   numerical and narrative evidence and current bindings. Owner review found
   execution-failure lineage/decision compatibility in its verifier; that
   owner merged the correction in PR #10 before this branch's final checks.
   This component never weakens that
   independent gate. Final delivery remains a separate parent decision.
4. **Preexecution guidance envelope.** Draft.3's `report_draft` requires an
   execution binding even for `missing_inputs`. Genuine pre-signoff guidance
   therefore remains an explicitly local result consumed by intake/parent;
   no fake execution is created to serialize it as a final report.
5. **Trusted application callbacks.** A real immutable artifact reader,
   current parent-ledger verifier, source/name adapters, independent semantic
   reviewer and supported focused LangChain humanizer must be wired by their
   respective owners. Test callbacks and generated mock artifacts establish
   none of those capabilities.

These are native integration/acceptance waits, not a measured model failure,
proof that the business problem is impossible, or authorization to close any
issue. DSC-29 changes no Linear status and delivers no real order list.
