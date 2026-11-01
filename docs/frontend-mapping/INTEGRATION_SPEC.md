# Integration spec — Suiro frontend over the governed backend

**Status:** draft for review · **Branch:** `feat/dsc-68-integration-spec` · **Base:** `nightly`

Companion to [`FRONTEND_TO_BACKEND_MAP.md`](./FRONTEND_TO_BACKEND_MAP.md). The map explains
*how the two sides correspond and where they don't*. This spec says *what we will build to join
them*, in what scope, and how we will know it works. The follow-on
[`INTEGRATION_PLAN.md`](./INTEGRATION_PLAN.md) turns this into PRs and
[`TASKS.md`](./TASKS.md) into checkable tasks.

> **Architecture note (supersedes narrower framing below).** See
> [`docs/architecture/AGNOSTIC_ENGINE.md`](../architecture/AGNOSTIC_ENGINE.md). The system is
> **problem-agnostic**: the engine holds no domain knowledge and evaluates rules supplied as
> **data**. The existing single-case backend is the **demo**, not the target. Current focus is the
> **end-to-end retail chain** (demand → forecasting → restocking → **suppliers/procurement** →
> inventory → pricing/markdown → assortment → fulfilment), not a single problem. Where this spec
> says "restocking", read it as the first built area of that chain; the service layer expresses
> retail as a supplied rule library (`service/retail/`) over a generic engine
> (`service/derive.py`, `service/rules.py`), with thresholds overridable and nothing baked in.

---

## 1. Problem

Two halves exist, neither executes the product end to end:

- The **frontend** (handoff zip) is a reference-only prototype of a customer-facing restocking
  app (5-step flow + report). "Do not ship its code."
- The **backend** (`src/suiroai/`) is a governed analytical engine — a 7-stage `ParentWorkflow`
  producing immutable, verified records — but per its README "does not execute the customer
  workflow… no server, no demo runner."

Nothing drives a question from upload to a reviewable order list. There is no HTTP surface, no
orchestration that steps a run through its stages, and no translation from the backend's
artifact records into the shapes the frontend expects (`types.d.ts`).

## 2. Goal

Stand up a **thin integration layer** that drives one `Analysis` through the **real** backend
stages and serves the resulting recommendations and report to a frontend, honouring the backend's
governance (approval, verification, immutable evidence) and the frontend's data contract
(`types.d.ts`). Deliver it as a **demoable end-to-end happy path first**, then fill gaps.

The integration layer is **new code in this repo** under `src/suiroai/service/` (name TBD in
plan). It calls existing modules; it does not fork their logic or re-implement business rules.

## 3. Scope

The work splits into two buckets (from the map §3). Both are **specified here**; the
**task list and first code target bucket A only**.

### Scope A — backend seam (this repo, this phase)

A1. **Orchestration driver.** A helper that advances a `ParentWorkflow` through the stage
sequence (`preparation → … → output_verification`), wiring the trusted callbacks
(`confirm_approval`, `review_release`, `review_evidence`) and a record store. For the demo path it
may consume the committed contract fixtures (`examples/contracts/v0.1.0/*`) where a full live run
is not yet wired, clearly labelled as mock provenance.

A2. **HTTP/API surface.** A minimal REST layer implementing the subset of `docs/05-data-model-and-api.md`
that has a backend seam (map §4):
`POST /analyses`, `POST/PATCH/DELETE …/files`, `GET …/readiness`, `POST …/approve-task`,
`GET …/model-run`, `POST …/report`, `GET …/report/{tab}`, `GET …/order-lines`,
`GET …/export.csv`. Authenticated and authorised per request (even if the identity model is a
stub this phase — see B1).

A3. **Record → view translation.** Pure functions turning backend records into frontend shapes:
`submission`→`Analysis`/`DataFile[]`, proposal gaps→`Readiness[]`, `evaluation_result`→`ModelResult[]`/`ModelRun`,
`quantity_result.orders[]`→`OrderLine[]`, `report_draft.findings/claims`→report tabs. One-way,
no business logic, fully unit-tested against the fixtures.

A4. **Server-side derived fields** the frontend needs but the order record lacks (map §2.4, §2.6;
rules in `docs/04-business-rules.md`): `coverWeeks`, line flags + priority (§4.3), supplier
aggregate minimums + status (§4.2), report-tab chart aggregation with completeness. Computed
server-side only; never trusted from a client (`docs/05` requirement).

A5. **Events.** The run-progress channel (`model_run.progress/done`) so step 3 can show progress
and completion survives reloads. SSE or polling; real, not a timer.

### Scope B — product tier (specified, later phases)

Each is absent from the backend contract (map §3) and will be its own phase:

- B1. Identity: workspace, people, roles, store access; server-enforced authz.
- B2. Live order-line editing (optimistic save, last-write-wins, editor, "Not saved").
- B3. Order-list approvals: per-store + owner sign-off, reset-on-edit, activity log.
- B4. Reminders, escalation, recurring schedule.
- B5. Notifications / bell, fed by real events.
- B6. Delivery: email + CSV export, recipient allow-list, store scope, idempotent send, history.
- B7. Stock alerts by category (§4.4).
- B8. Ideas / discovery web search, server-side, with the §4.10 privacy brief.

### Non-goals (this phase)

- Not shipping the prototype's JS/HTML. It stays the visual reference.
- Not re-implementing business rules that already live in `replenishment`/`modeling`; A4 adds only
  what the backend genuinely does not compute.
- Not changing the backend's temporal constants (the fixed 2025-11-30 case). "Next week"
  parameterisation is a tracked gap (map §3.10), out of scope here.
- Not building B1–B8 in this phase.

## 4. The end-to-end happy path (first demoable slice)

The slice that the task list and first code will deliver:

1. Create an analysis from a question and attach files (roles mapped per map §2.1, incl.
   `dictionary`). → `submission`.
2. Show readiness; when ready, approve the task. → proposal/approval → `start(execution_contract)`.
3. Run the stages and show progress; on completion, surface model comparison + recommended.
   → `evaluation_result`.
4. Build the report; serve summary + data tabs from `report_draft`. → `draft_success`.
5. List the order lines (from `quantity_result.orders[]`) with server-computed cover, flags and
   supplier-minimum status; expose read-only CSV export scoped to the caller. `output_verification`
   must be `delivery_allowed` before export/report success is served.

Edit/approve/deliver interactions beyond read-only are **stubbed** this phase (belong to B2/B3/B6).

## 5. Requirements (traceable)

Each requirement cites its source so acceptance is checkable.

| ID | Requirement | Source |
| --- | --- | --- |
| R1 | File roles map 1:1 incl. `dictionary` + review-context confirmation | map §2.1; `intake/roles.py` |
| R2 | Readiness derives from proposal gaps (`material`, `blocks`) | `04 §4.9`; schema `gap` |
| R3 | Four model metrics defined exactly (WAPE, MAE, recall, 1−precision); baseline always shown | `04 §4.7` |
| R4 | Recommended = best accuracy that also catches most shortages | `04 §4.7` |
| R5 | Suggested qty authoritative from `quantity_result`; frontend formula only illustrative | map §2.4 |
| R6 | Order exceptions (`timing_ambiguity`, `shortage`, …) surfaced, not hidden | `replenishment/calculation.py` |
| R7 | Line flags + priority (≤2 shown, +N more) computed server-side | `04 §4.3` |
| R8 | Supplier aggregate minimums + top-up computed server-side | `04 §4.2` |
| R9 | Report success only when `output_verification == delivery_allowed`; failures carry no orders | `verification/*`; `reporting/drafts.py` |
| R10 | Every read/write authenticated + authorised; derived fields never trusted from client | `05 Security` |
| R11 | Search/model output treated as untrusted; escape text; only http/https links | `05 Security`; `04 §4.10` |
| R12 | Run is a job: progress survives reload; completion notifies even if nobody connected | `05 Reliability` |
| R13 | Order lines: server-side filter/sort/group/paginate with group totals | `05 Performance` |
| R14 | Formats (currency/number/date) and time zone from workspace settings | `05 i18n` |

## 6. Acceptance

The phase is done when the §4 slice runs against the real backend modules (fixtures where a live
run isn't wired, labelled mock) and:

- The §4.11 acceptance examples relevant to this slice pass as tests, specifically:
  - Ex 1 (suggestion arithmetic — asserted against `quantity_result`, R5),
  - Ex 2 & 3 (supplier minimum below, top-up — R8),
  - Ex 6 (perishable at-risk — R7 flag),
  - Ex 4 (delivery locked until verified/approved — R9),
  - Ex 8 (run finishes while user elsewhere → completion event — R12),
  - Ex 10 (Viewer: export/edit disabled — R10).
- Translation functions (A3) round-trip each committed fixture without loss or fabrication.
- `GET /order-lines` returns server-computed `coverWeeks`, `flags`, and supplier status; a client
  cannot override them.
- CSV export is scoped to the caller's stores.

## 7. Risks / open decisions

1. **Two suggested-qty formulas** (map §2.4). Decision assumed: backend authoritative (R5).
   Confirm before UI shows any number.
2. **Temporal mismatch** — demo is the 2025-11-30 case; "next week" wording in the UI is
   cosmetic until §3.10 is funded.
3. **Live run vs fixtures** — a full live `ParentWorkflow` run needs real inputs and the trusted
   reviewers; where not available this phase uses fixtures. The seam is identical so swapping in a
   live run later is additive.
4. **Identity stub** — A2 authorises requests but B1 is not built; the stub must fail closed
   (deny by default) so it is safe to replace.

---

*Next: [`INTEGRATION_PLAN.md`](./INTEGRATION_PLAN.md) breaks scope A into ordered PRs; scope B is
sketched as later phases.*
