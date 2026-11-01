# Integration plan — PR breakdown

**Status:** draft for review · **Branch:** `feat/dsc-69-integration-plan` · **Base:** `nightly`

Turns [`INTEGRATION_SPEC.md`](./INTEGRATION_SPEC.md) into ordered, PR-sized work. Scope A (backend
seam) is planned PR-by-PR and built first; scope B (product tier) is sketched as later phases.
Granular checkable items for Phase A live in [`TASKS.md`](./TASKS.md).

Conventions (observed from the repo): branch `feat/dsc-NN-slug`, commit
`type(area): summary (DSC-NN)`, PRs target `nightly`. Each PR below is independently reviewable and
mergeable, with tests, and depends only on earlier PRs.

---

## Phase A — backend seam (this phase)

Target package: `src/suiroai/service/` (new). It **calls** existing modules; it never forks their
logic. Tests under `tests/service/`. Fixtures reused from `examples/contracts/v0.1.0/*`.

### A-PR1 · `service` package skeleton + record store adapter · DSC-70
- **Scope:** create `src/suiroai/service/__init__.py`; a thin in-memory/record store the
  orchestration driver can hand to `ParentWorkflow` (satisfying the `store` interface it uses:
  `put_record`, `read_record`, `put_bytes`, `read_bytes`, `read` by ref). No HTTP yet.
- **Files:** `service/__init__.py`, `service/store.py`, `tests/service/test_store.py`.
- **Acceptance:** round-trips a fixture record and its bytes; rejects unknown refs. (R10 fail-closed.)
- **Depends on:** spec (#33).

### A-PR2 · Orchestration driver over `ParentWorkflow` · DSC-71
- **Scope:** `service/orchestrator.py` — advances a workflow through
  `preparation → … → output_verification`, wiring trusted callbacks. For the demo path, load a
  committed fixture bundle (`examples/contracts/v0.1.0/successful_analysis.json`) into the store and
  expose stage state + `checkpoint()`. Mock provenance surfaced, never hidden (spec §3 A1).
- **Files:** `service/orchestrator.py`, `tests/service/test_orchestrator.py`.
- **Acceptance:** drives the `successful_analysis` fixture to a state exposing a `report_draft`
  and `quantity_result`; a `missing_inputs` fixture stops at readiness with material gaps (R2);
  `validation_failed` / `execution_failed` fixtures yield a failure report with **no orders** (R9).
- **Depends on:** A-PR1.

### A-PR3 · Record → view translation (read models) · DSC-72
- **Scope:** `service/views.py` — pure functions to `types.d.ts` shapes:
  `submission`→`Analysis`+`DataFile[]` (roles per map §2.1, incl. `dictionary`),
  proposal gaps→`Readiness[]`, `evaluation_result`→`ModelResult[]`+`ModelRun`+`recommendedId`,
  `quantity_result.orders[]`/`exceptions[]`→`OrderLine[]`, `report_draft`→summary/data tabs.
  Text escaped; only http/https links (R11). No business logic here.
- **Files:** `service/views.py`, `tests/service/test_views.py`.
- **Acceptance:** each committed fixture round-trips without loss or fabrication; metric labels
  match §4.7 exactly (R3); recommended = best-accuracy-also-most-shortages (R4); exceptions appear
  as a distinct line state (R6).
- **Depends on:** A-PR2.

### A-PR4 · Server-side derived fields · DSC-73
- **Scope:** `service/derive.py` — compute what the order record lacks, per `docs/04`:
  `coverWeeks`; line flags + priority with ≤2-shown/+N-more (§4.3); supplier aggregate minimums,
  status and top-up (§4.2). Pure, unit-tested against the rules’ acceptance examples. Values are
  server-authoritative (R7, R8, R10).
- **Files:** `service/derive.py`, `tests/service/test_derive.py`.
- **Acceptance:** §4.11 Ex 2 & 3 (supplier minima + top-up) and Ex 6 (perishable at-risk) pass as
  tests; a client-supplied flag/cover is ignored.
- **Depends on:** A-PR3.

### A-PR5 · HTTP API — analyses, files, readiness, approve-task · DSC-74
- **Scope:** `service/api/` — REST for the upload→approve arc:
  `POST /analyses`, `POST/PATCH/DELETE …/files`, `GET …/readiness`, `POST …/approve-task`.
  Auth stub that **denies by default** (R10). Framework per repo norms (decide in A-PR5; likely
  stdlib/`wsgiref` or a tiny dep requested via DSC-3 ownership — see note).
- **Files:** `service/api/__init__.py`, `service/api/analyses.py`, `tests/service/test_api_intake.py`.
- **Acceptance:** create→add files→readiness→approve-task drives a real `receive_submission` →
  `present_proposal` → `record_approval` → `start`; readiness reflects gaps (R2); unauthorised
  request is denied.
- **Depends on:** A-PR2, A-PR3. **Dependency note:** any web framework must be requested through
  the DSC-3 manifest owner (per repo README); A-PR5 will propose the minimal choice, not add it
  silently.

### A-PR6 · HTTP API — model-run, report, order-lines, export · DSC-75
- **Scope:** `GET …/model-run`, `POST …/report`, `GET …/report/{tab}`,
  `GET …/order-lines` (server-side filter/sort/group/paginate with group totals, R13),
  `GET …/export.csv` (scoped to caller, R10). Report success gated on `delivery_allowed` (R9).
- **Files:** `service/api/run.py`, `service/api/orders.py`, `tests/service/test_api_report.py`.
- **Acceptance:** §4.11 Ex 4 (delivery locked until verified) and Ex 10 (Viewer: export disabled)
  pass; order-lines paginate with correct group totals; CSV scoped.
- **Depends on:** A-PR4, A-PR5.

### A-PR7 · Run-progress events · DSC-76
- **Scope:** `service/events.py` — progress/done channel (SSE or long-poll) so step 3 shows live
  progress and completion is recorded even if nobody is connected (R12).
- **Files:** `service/events.py`, `tests/service/test_events.py`.
- **Acceptance:** §4.11 Ex 8 (run finishes while user elsewhere → completion recorded/notified).
- **Depends on:** A-PR2.

### A-PR8 · End-to-end happy-path test + demo runner · DSC-77
- **Scope:** `tests/service/test_e2e_happy_path.py` exercising the full spec §4 slice through the
  API; a small `service/demo.py` entrypoint wiring it to a fixture so the frontend/demo can hit it.
- **Acceptance:** the §4 slice runs end to end; all spec §6 acceptance items green.
- **Depends on:** A-PR6, A-PR7.

**Phase A order:** A-PR1 → A-PR2 → A-PR3 → A-PR4 → A-PR5 → A-PR6 → A-PR7 → A-PR8.
A-PR3/A-PR4 and A-PR7 can proceed in parallel with the API PRs once A-PR2 lands.

---

## Phase B — product tier (later, sketched)

Each becomes its own spec+plan when funded; listed here with suggested DSC IDs and dependency on
Phase A’s API.

| Phase | Area | Spec ref | Depends on |
| --- | --- | --- | --- |
| B1 | Identity: workspace/people/roles/store authz (replaces the A-PR5 stub) | spec §3 B1; map §3.1 | A-PR5 |
| B2 | Live order-line editing (optimistic, last-write-wins, "Not saved") | B2; map §3.2 | A-PR6, B1 |
| B3 | Order-list approvals: per-store + owner, reset-on-edit, activity log | B3; map §3.3 | B1, B2 |
| B4 | Reminders, escalation, recurring schedule | B4; map §3.4 | B3 |
| B5 | Notifications / bell from real events | B5; map §3.6 | A-PR7, B3 |
| B6 | Delivery: email + CSV, allow-list, scope, idempotent send, history | B6; map §3.7 | B1, B3 |
| B7 | Stock alerts by category | B7; map §3.8 | A-PR4 |
| B8 | Ideas / discovery web search (server-side, §4.10 privacy) | B8; map §3.5 | A-PR5, legal/privacy (`docs/07`) |

Also tracked (backend change, not a product-tier add): **temporal parameterisation** to let the
app mean "next week" rather than the fixed 2025-11-30 case (map §3.10) — large, scheduled
separately.

---

## Testing & CI expectations (all PRs)

- Unit tests co-located under `tests/service/`; reuse `examples/contracts/v0.1.0/*` fixtures.
- Business-rule PRs (A-PR4) assert the exact `docs/04-business-rules.md §4.11` examples.
- No raw customer data, credentials or generated artifacts committed (repo README rule).
- New runtime dependencies only via the DSC-3 manifest owner; propose, don't add silently.

---

*Next: [`TASKS.md`](./TASKS.md) expands Phase A into checkable tasks and the code PRs begin with
A-PR1 (DSC-70).*
