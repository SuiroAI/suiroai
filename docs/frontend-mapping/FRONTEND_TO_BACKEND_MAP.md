# Frontend ↔ Backend mapping

This document maps the **Suiro AI dev-handoff frontend** (the HTML prototype and its specs,
packaged in `SuiroAI_Drive_Folder.zip` on `main`) to the **existing Python backend**
in `src/suiroai/`.

It is a reading aid for whoever wires the product shell to the analytical engine. It makes
no code changes. Formulas and field names are quoted from the sources, not invented.

## Sources used

Frontend (from the handoff zip, `Dev Files/suiro-dev-handoff/`):
- `prototype/suiro-ai-prototype.html` and `src/app.js` — the working prototype (state object `S`, `render()`).
- `docs/03-screens-and-flows.md` — screen/flow spec.
- `docs/04-business-rules.md` — business logic and metric definitions.
- `docs/05-data-model-and-api.md` — a **proposed** REST API and entity model.
- `docs/types.d.ts` — the frontend data contract (TypeScript).

Backend (this repo):
- `src/suiroai/contracts/schema/retail-contract.schema.json` — the immutable artifact-record contract (JSON Schema Draft 2020-12).
- `src/suiroai/parent/workflow.py` — `ParentWorkflow`, the governed stage controller.
- `src/suiroai/intake/{roles,conversation,receipt}.py` — understanding + proposal + approval.
- `src/suiroai/modeling/{evaluation,metrics,models,...}.py` — development evaluation, freeze, final validation.
- `src/suiroai/replenishment/calculation.py` — forecast → candidate order quantities.
- `src/suiroai/reporting/drafts.py` — composes the customer-facing narrative/report.
- `src/suiroai/verification/*` — independent verification before delivery.
- `examples/contracts/v0.1.0/*.json` — concrete record fixtures (`successful_analysis`, `missing_inputs`, `validation_failed`, `approved_execution`, `execution_failed`).

---

## 0. The headline: two contracts, one seam

The frontend handoff and the Python backend are **not yet a matched client/server pair**.
They describe the same business problem at two different altitudes:

| | Frontend handoff | Python backend |
| --- | --- | --- |
| Shape | Customer-facing multi-tenant SaaS: REST + SSE, workspaces, roles, email, reminders, Ideas search | A single governed analytical pipeline for **one historical retail restocking case** |
| Unit of work | An `Analysis` the user drives interactively | One task → approval → run, one outstanding stage at a time (`ParentWorkflow`) |
| State model | Mutable entities edited live (`PATCH /order-lines/{id}`) | Immutable, hash-referenced artifact **records** validated against a schema |
| Time model | "Next week", a live prototype clock | Fixed as-of **2025-11-30**; train/validation/holdout cutoffs are contract constants |
| Delivery | Download / email / schedule to recipients | "delivery_allowed" only after independent verification of the run's evidence |
| Status today | Reference-only prototype ("Do not ship its code") | README: "it does not execute the customer workflow… no server, no demo runner" |

So the mapping has **two layers**:
1. **Real seams** — frontend concepts that correspond to a backend stage or record (§2).
2. **Gaps** — frontend features the backend does not model at all; these need either a new product-tier service or a decision to descope (§3).

The backend's own vocabulary is the **7-stage run** in `parent/workflow.py`:

```
preparation
→ initial_baseline_evaluation
→ llm_features
→ comparison_and_freeze
→ final_validation
→ recommendations
→ output_verification
```

Everything the user sees in steps 1–5 of the prototype is produced (or should be) by these stages.

---

## 1. Flow-level mapping (prototype step → backend)

The prototype has a 5-step stepper (`STEPS` in `app.js`). Here is how each maps.

| Prototype step | Frontend state / proposed endpoint | Backend counterpart |
| --- | --- | --- |
| **1. Upload data** (`s1`) | `S.question`, `S.files[]`, `addFiles()`, `guessRole()`; `POST /analyses`, `POST /analyses/{id}/files` | `intake` **submission** record (`submission_file[]` with `source_role`); created via `ParentWorkflow.receive_submission(submission, external_refs=…)` |
| **2. Confirm task** (`s2`) | `readiness()` table, `pbCard()` decision note; `GET /analyses/{id}/readiness`, `POST /analyses/{id}/approve-task` | `intake.roles` **understanding** → **task_proposal** (`present_proposal`) → **task_approval** (`record_approval`); readiness ≈ proposal `readiness`/`gaps` |
| **3. Test models** (`s3`) | `MODELS[]`, `startModels()`, `ModelRun`; `GET /analyses/{id}/model-run`, `PUT …/selection` | Stages `initial_baseline_evaluation`, `llm_features`, `comparison_and_freeze` (`modeling.evaluation`), then `final_validation` |
| **4. Business report** (`s4`) | report tabs (`summary/data/customers/products/trends/ideas`); `POST /analyses/{id}/report`, `GET …/report/{tab}` | `recommendations` stage → `reporting.drafts.draft_success()` produces `report_draft` with `claims`, `findings`, `orders` |
| **5. Review & deliver** (`s5`) | order list, approvals, delivery; many endpoints | `recommendations` `quantity_result` (per-key orders) + `output_verification` (`verification/*`) gating "delivery_allowed" |

Note the **approval is in a different place** on each side. The prototype asks for approval
*twice*: at step 2 ("Approve and analyze", which just starts the run) and at step 5 (per-store +
owner sign-off of the final order list). The backend's single formal approval
(`task_approval` → `start(execution_contract)`) corresponds to the **step-2** gate. The
backend has **no** per-store / owner sign-off of edited quantities — that is a frontend/product
construct (see §3.3).

---

## 2. Entity and field mapping (the real seams)

### 2.1 Files and roles — near 1:1

Frontend `FileRole` (`types.d.ts`) ↔ backend `submission_file.source_role` (schema + `intake/roles.py` `NEEDS`):

| Frontend `FileRole` | Backend `source_role` | Backend need key (`roles.py`) |
| --- | --- | --- |
| `Sales history` | `transactions` | `sales_history` |
| `Stock on hand` | `usable_stock` | `usable_stock` |
| `Incoming shipments` | `inbound_ledger` | `inbound_position` |
| `Supplier rules` | `ordering_policy` | `ordering_rules` |
| `Other` | `other` | — |
| *(no UI yet)* | `dictionary` | `quantity_meaning` |

Gaps to reconcile:
- Backend also expects a **`dictionary`** file (field meanings / units) and an explicit
  **`review_context`** confirmation. The prototype has no first-class UI for either; `guessRole()`
  would need a "Data dictionary" option, and the fixed 2025-11-30 review context needs surfacing.
- Backend `intake/roles.py` is emphatic: `Inventory_Level` is **not** verified usable stock,
  `Delivery_Days` is **not** supplier lead time, absent inbound rows are **not** "no inbound".
  The prototype's cheerful `guessRole()` heuristics must not imply these meanings are confirmed.

### 2.2 Readiness ↔ proposal gaps

Frontend `readiness()` returns rows with `state: "ok"|"warn"|"bad"`. Backend equivalent is the
**understanding/proposal**: `understanding_schema()` yields `coverage[]`, `assumptions[]`, `gaps[]`;
the `gap` record (schema) has `material`, `blocks` (`approval|execution|quantities|report`), and
`request_to_user`. A `bad`/blocking readiness row ≈ a **material gap** that `blocks: ["execution"]`.
`draft_missing_inputs()` in `reporting/drafts.py` is the backend's "show what's missing" path and
already emits per-gap customer text — a natural source for the readiness UI.

### 2.3 Models and metrics

Frontend `ModelResult` (`types.d.ts`) and the four headline metrics map to the backend's
development evaluation (`modeling/evaluation.py`, `modeling/metrics.py`) and the fixed metric
definitions in `docs/04-business-rules.md §4.7`:

| Frontend field | Meaning (per §4.7) | Backend source |
| --- | --- | --- |
| `accuracy` | 100% − WAPE | metric over held-back weeks (`metrics.py`) |
| `typicalErrorUnits` | mean absolute error | same |
| `shortagesCaught` | recall of would-run-out weeks | same |
| `unneededOrders` | 1 − precision of reorder suggestions | same |
| `recommendedId` | best accuracy that also catches most shortages | `comparison_and_freeze` → `evaluation_result.frozen.selected_candidate_id` |

Important differences:
- The prototype shows **5 named models** (`avg`, `lin`, `cur`, `rf`, `xgb`) with illustrative
  scores and a timer. The backend compares **candidate specs** (`CandidateSpec`) over **rolling
  folds** with strict chronology (`_validate_folds`: training ≤ origin, labels available by CUTOFF),
  then **freezes one** before touching the holdout. There is no list of five branded algorithms in
  the contract — the UI's model names would be a presentation layer over whatever candidates the
  run actually fit.
- The prototype's "Existing business method (`cur`)" baseline maps to the backend's **baseline**
  (`evaluation_result.baseline_scores`), always shown (per §4.7 "Always show the user's existing
  method as a baseline").
- The prototype's `ModelRun.state` (`queued|running|done|failed`) maps to `ParentWorkflow.state`
  progressing through stages; completion/notify would come from real events, not `setInterval`.

### 2.4 Order lines — same domain, different governance

This is the richest seam. Frontend `OrderLine` (`types.d.ts`) ↔ backend
`quantity_result.orders[]` rows (`replenishment/calculation.py` `_calculate_key`).

| Frontend `OrderLine` | Backend order row field | Notes |
| --- | --- | --- |
| `productId` + `store` | `key` = `{source_namespace, product_id, store_id}` | backend keys by namespace too |
| `onHand` | `usable_on_hand_quantity` | |
| `incoming` | `eligible_receipt_quantity` (+ `on_order_summary_quantity`) | backend only counts receipts arriving within the horizon |
| `suggestedQty` | `rounded_order_quantity` | see formula note below |
| `qty` (user choice) | `approved_order_quantity` | backend value is `None` until a parent proceed; **the user does not freely edit it** |
| `coverWeeks`, `weeklyPace`, `trendPct` | — (not in the order record) | derived/presentation; backend works in daily forecast + horizon |
| `lineCost`, `flags`, `reviewed`, `note`, `editedBy` | — | **not modeled** by backend (product-shell concepts) |
| `lastRestockQty/Date`, `daysSinceLastSale`, `expiryDate` | — | not in the order record |
| `forecast_horizon_start/end` | `forecast_horizon_start`/`_end` | backend is horizon-based (`lead + review` days), not "next week" |

**Formula reconciliation — read this carefully.** The two sides compute order quantities with
*different* models:

- Frontend (`docs/04-business-rules.md §4.1`, `app.js`):
  `need = weekly × (1 + trend/100) × 2.5 − onHand − incoming`;
  `suggested = ceil(round(need)/pack) × pack`. A simple weekly-pace × 2.5-week cover rule.
- Backend (`replenishment/calculation.py`): sums a **daily** frozen forecast over a
  `lead + review` horizon, subtracts usable stock and horizon-eligible receipts, adds
  `Safety_Stock_Qty`, then rounds up to `Order_Multiple_Qty` respecting `Minimum_Order_Qty` — with
  per-day balance checks that withhold a key as `timing_ambiguity`/`shortage` rather than guess.

These are not the same number and will not always agree. **Decision needed:** the product must pick
one source of truth for "suggested". The backend's is the governed, verifiable one; the frontend's
is the illustrative prototype rule. The recommendation is to treat the backend `quantity_result` as
authoritative and render the frontend formula only as an explanatory approximation (if at all).

Also: the backend's **exceptions** (`quantity_result.exceptions[]`, e.g.
`timing_ambiguity`, `shortage`, `missing_or_duplicate_stock_or_policy`) have no direct prototype
equivalent. They should surface as a distinct row state ("can't recommend a quantity, here's why"),
not be silently hidden.

### 2.5 Suppliers and minimums

Frontend `Supplier` (`minUnits`, `minValue`, `logic`) and the supplier-minimum drawer (`supStat()`,
`docs/04-business-rules.md §4.2`) are a **frontend/product** construct. The backend's
`ordering_policy` operates per product-store (`Minimum_Order_Qty`, `Order_Multiple_Qty`,
`Supplier_Lead_Time_Days`, `Review_Period_Days`, `Safety_Stock_Qty`) — there is **no supplier-level
aggregate minimum** in the contract. The "supplier below minimum across all stores" check, top-up
suggestion, and owner-editable supplier minimums would be new backend capability (see §3).

### 2.6 Report tabs and alerts

Frontend report (`s4`) tabs map loosely:
- **Summary / Data / Products / Trends** draw on the forecast + history. In the backend these are
  `report_draft.findings[]` (audience `final_report`) and `claims[]` assembled by
  `reporting/drafts.draft_success()` from preparation EDA, features, comparison and unseen
  validation. The prototype computes charts client-side from `DAYS[]`; production must aggregate
  server-side (`GET …/report/{tab}`, `docs/05 Performance`).
- **Customers** — the prototype already shows "Not enough data" unless a preview toggle is on. This
  matches backend reality (no customer IDs in scope). Keep the toggle out of production
  (`docs/04-business-rules.md §4.9`).
- **Ideas** (web search) — **no backend counterpart at all** (see §3.5).
- **Grouped alerts** (`attentionCard`, `ReportAlert`) are derived from `OrderLine.flags`, which the
  backend doesn't produce. Flag computation (`§4.3`) must move server-side.

### 2.7 Verification and "delivery allowed"

The frontend's final "Send report?" confirmation is cosmetic. The backend has a **hard gate**:
`output_verification` must return `decision: "delivery_allowed"` (independent verifier, `verification/*`)
before `reporting.drafts` will emit a success report; a failed/validation-failed run can only produce
a `draft_validation_failure` / `draft_execution_failure` with **no orders**. The product's delivery
UI must respect this: there is no "send the order list" unless the run verified.

---

## 3. Gaps — frontend features with no backend model

These are in the handoff/prototype but **absent from the current Python contract**. Each needs a
decision: build a new product-tier service, extend the backend, or descope.

1. **Multi-tenant workspace, people, roles, store access.** `Workspace`, `Person`, `Role`,
   `StoreApprovers` (`types.d.ts`, `docs/05 Entities`) — the backend is single-task and has no
   identity/authz model. `docs/05` is explicit this must be server-enforced. **New service.**

2. **Live order-line editing.** `PATCH /order-lines/{id}` with optimistic save, last-write-wins,
   editor name, "Not saved" (`docs/05 Reliability`). Backend order quantities are immutable records
   approved by the parent, not user-editable fields. **Product-tier state store needed**, with a
   defined relationship to the authoritative `quantity_result`.

3. **Per-store + owner approval of the edited list, with reset-on-edit.** `Approval`,
   `§4.5`, acceptance examples 4–5. The backend's one approval is the *task* approval
   (start-the-run). The *order-list* sign-off workflow is entirely product-tier. **New service.**

4. **Reminders, escalation, scheduling.** `ReminderSettings`, `Schedule`, `§4.5`–`§4.6`. The
   prototype simulates with a clock. **New scheduled-jobs service.**

5. **Ideas / web-search discovery.** `Opportunity`, `discCard`, `§4.10`, `POST /discovery/searches`.
   The prototype calls Anthropic directly from the browser. Needs a **server-side search service**
   with the privacy brief of `§4.10` (only category names/price ranges/regions/guidelines sent;
   never sales, customers, product or supplier names). **New service, gated on legal/privacy
   per `docs/07`.**

6. **Notifications / bell.** `Notification`, `GET /notifications`. **New service** (fed by real
   events: `model_run.done`, `approval.changed`, stock alerts).

7. **Delivery, email, CSV export scope.** `DeliveryRecord`, `GET …/export.csv`, idempotent send,
   per-recipient status. Backend only decides *whether delivery is allowed*, not how it's sent.
   **New delivery service**, must enforce recipient allow-list and store scope server-side.

8. **Stock alerts by category** (`AlertSettings`, `CategoryRule`, `§4.4`) and **supplier-level
   minimums** (`§4.2`). Not in the contract's per-key `ordering_policy`. **Backend extension or
   product-tier computation.**

9. **Supplier aggregate minimums, top-up suggestions, owner edits** (§2.5 above). **Backend
   extension.**

10. **Live clock / "next week" semantics.** Backend is pinned to as-of 2025-11-30. Productionising
    for "next week" means parameterising the temporal plan — currently hard-constrained in the
    schema (`temporal_plan` consts) and `modeling` (`CUTOFF`). **Significant backend change.**

---

## 4. Endpoint → backend-call sketch (for the eventual API layer)

For the endpoints in `docs/05` that *do* have a backend seam, the wiring is roughly:

| Proposed endpoint | Backend call(s) |
| --- | --- |
| `POST /analyses` + `POST …/files` | build a `submission` record → `ParentWorkflow.receive_submission(submission, external_refs=…)` |
| `GET …/readiness` | `intake` understanding/proposal → readiness from `proposal.gaps`; or `reporting.drafts.draft_missing_inputs()` |
| `POST …/approve-task` | `ParentWorkflow.present_proposal()` → `record_approval()` → `start(execution_contract)` |
| `GET …/model-run` (+ SSE) | drive stages via `issue_stage()` / `parent_review()`; expose `ParentWorkflow.state` + `checkpoint()` events |
| `POST …/report`, `GET …/report/{tab}` | after `recommendations`, call `reporting.drafts.draft_success()`; serve `report_draft.findings/claims` |
| `GET …/order-lines` | read `quantity_result.orders[]` (+ `exceptions[]`); server-side filter/sort/group/paginate |
| `GET …/suppliers/minimums` | **new** aggregation over orders (no backend equivalent today) |
| `GET …/approvals`, `POST …/approvals/{scope}` | **new** product-tier approval store (not `ParentWorkflow`) |
| delivery / notifications / discovery / schedule | **new** services (§3) |

`output_verification` → `decision == "delivery_allowed"` is the precondition for any delivery
endpoint returning success.

---

## 5. Recommended next steps

1. **Agree the source of truth for order quantities** (§2.4). Suggest: backend `quantity_result`
   authoritative; frontend formula shown only as an approximation.
2. **Add the `dictionary` file role and review-context confirmation** to the upload UI (§2.1).
3. **Move flag/alert/supplier-minimum computation server-side** (§2.5, §2.6) — either extend the
   backend or define a product-tier compute service with tests mirroring `docs/04-business-rules.md`.
4. **Scope the product tier** that the backend does not cover (identity/roles, order-line editing,
   order-list approvals, reminders, notifications, delivery, discovery) as a separate service —
   this is the bulk of the handoff's API surface (§3).
5. **Decide on temporal parameterisation** (§3.10) before "next week" can mean anything other than
   the fixed 2025-11-30 case.

---

*This map reflects the repository at the time of writing. The frontend side is reference-only
(`handoff/README.md`: "Do not ship its code"); the backend side "does not execute the customer
workflow" yet (`README.md`). Treat this as a planning artifact, not a built integration.*
