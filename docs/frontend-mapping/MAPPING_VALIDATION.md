# Frontend mapping — validation against the current backend and open PRs

**Status:** validation record. Confirms where
[`FRONTEND_TO_BACKEND_MAP.md`](./FRONTEND_TO_BACKEND_MAP.md) still holds against the real backend
and the open PRs, and flags the few items to update. No code or mapping prose changed here; this is
a reviewable finding list.

## What was validated against

- Backend on `nightly` plus the open feature PRs **#31** (DSC-66: dscraft backend + seeded-stochastic
  quantile model & service-level safety stock) and **#32** (DSC-67: EDA through `dscraft.eda`).
- The contract schema `src/suiroai/contracts/schema/retail-contract.schema.json` and the modules the
  mapping cites (`intake/roles.py`, `modeling/metrics.py`, `replenishment/calculation.py`,
  `reporting/drafts.py`).
- Full test suite run: **602 passed, 37 skipped, 0 failures** with the portability fix (#35)
  applied; the 168 bare-`nightly` failures are entirely the `/private/tmp` hardcoding (#35), not
  logic — see §Portability.

## Still valid (no change needed)

- **§2.1 File roles.** `FileRole` ↔ `source_role` mapping (incl. the `dictionary` and
  `review_context` gaps) is unchanged. `intake/roles.py` still carries the "Inventory_Level is not
  usable stock / Delivery_Days is not lead time / absent inbound ≠ no inbound" cautions. ✓
- **§2.2 Readiness ↔ proposal gaps.** `gap` record fields (`material`, `blocks`, `request_to_user`)
  and `draft_missing_inputs()` unchanged. ✓
- **§2.4 Order lines.** Every order-row field the mapping cites still exists: `key`,
  `forecast_quantity`, `usable_on_hand_quantity`, `eligible_receipt_quantity`,
  `rounded_order_quantity`, `approved_order_quantity`, `safety_stock_quantity`,
  `order_multiple`, `minimum_positive_order_quantity`, horizon dates. The authoritative-quantity
  point (R5) and exceptions-as-distinct-state (R6) hold. ✓
- **Record kinds.** All kinds the mapping references (`submission`, `task_proposal`,
  `task_approval`, `evaluation_result`, `quantity_result`, `report_draft`, `output_verification`,
  `final_validation_result`) are present in the schema. #31/#32 changed **computation only**; the
  DSC-24 contract is untouched (confirmed in #32's own notes and by diff — neither PR edits
  schema/contract files). ✓
- **Delivery gate (§2.7).** `output_verification == delivery_allowed` is still the precondition for
  a success report; failures still carry no orders. ✓

## Items to update in the mapping

1. **§2.3 metrics table overstates the correspondence.** The backend (`modeling/metrics.py`) computes
   **`mae`** (always) and **`wape`** (optional, `include_wape`). It explicitly does **not** compute
   recall ("shortages caught") or precision ("unneeded orders") — the module docstring even says
   "No MAPE and no cross-SKU pooled WAPE." So of the frontend's four headline metrics, only
   **accuracy (100−WAPE)** and **typical error (MAE)** have a backend source; **shortages caught**
   and **unneeded orders** do not exist in the backend today. The mapping's §2.3 table should mark
   those two as *not produced by the backend* (a gap), consistent with how §2.3's prose already
   hedges ("generic metrics the backend carries"). **Action:** downgrade the two rows to "gap —
   not computed" rather than implying a 1:1 source.

2. **§2.4 safety stock is now richer (PR #31).** The order row's `safety_stock_quantity` is now the
   **effective** safety applied, and `replenishment/calculation.py` adds deterministic
   **service-level (quantile) safety stock** with audit fields `policy_safety_stock_quantity`,
   `quantile_safety_stock_exact`, `effective_safety_stock_exact`, `safety_stock_basis`
   (`"policy"` vs quantile). The mapping should note that safety stock may be **model-derived and
   deterministic**, not just the fixed policy value — relevant if the UI explains "why this
   quantity". **Action:** add a line to §2.4 noting the service-level safety-stock basis.

3. **Deterministic data science (PRs #31/#32) replaces the Codex-authored path.** The mapping's §0
   describes the backend as a governed pipeline; it should note that the analysis is now
   **first-party deterministic data science via `dscraft`** (seeded-stochastic modeling, KLL-sketch
   EDA), which is the MVP's "real data science coding" replacing Codex. **Action:** one sentence in
   §0 / §2.3 pointing at dscraft as the DS backend.

## Portability (validation of #35/#36, not mapping)

- Bare `nightly` fails 168 tests purely on hardcoded `dir="/private/tmp"` (macOS-only). With **#35**
  applied the suite is fully green. **#36** removes the `/Users/ceverson` and `/opt/anaconda3`
  hardcodes from `native_profile.py` behind env vars, keeping the macOS seatbelt semantics gated.
  Both are validated and needed for the OpenShift/universal target; they do not affect the mapping.

## Net

The frontend↔backend mapping is **sound and current** in its structure and all record/field claims.
Three small updates (two metric rows → gaps, a safety-stock note, a dscraft note) would bring it
fully in line with the deterministic-DS backend. None are blocking; the mapping does not misstate
anything that would mislead an implementer, given its existing "never guess / gap" framing.
