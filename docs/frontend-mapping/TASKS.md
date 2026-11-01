# Phase A task list (working doc)

Working checklist for me to drive Phase A code (scope A of
[`INTEGRATION_SPEC.md`](./INTEGRATION_SPEC.md), PRs in
[`INTEGRATION_PLAN.md`](./INTEGRATION_PLAN.md)). Each `A-PRn` ships as its own **code** PR into
`nightly`. These planning docs are internal working artifacts, not standalone review deliverables —
they travel with the first code PR.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done.

## A-PR1 · service skeleton + fixture loader (DSC-70)
Note: the repo already has a production content-addressed store at
`src/suiroai/integration/artifacts.py::ArtifactStore` with exactly the
`put_bytes`/`read_bytes`/`put_record`/`read_record` interface `ParentWorkflow` uses. We **reuse**
it rather than writing a parallel store. A-PR1 becomes a store factory + fixture loader.
- [x] confirm `ParentWorkflow` store interface (reads `store.put_record/read_record/put_bytes/read_bytes`)
- [x] confirm `ArtifactStore` already satisfies that interface
- [x] `src/suiroai/service/__init__.py` (package marker; docstring: only *calls* backend modules)
- [x] `src/suiroai/service/store.py` — `open_store(root)` factory over `ArtifactStore`; `load_fixture_bundle(store, path)` validates the bundle + each record and stores records + external byte artifacts, returning an index by kind; fail-closed on unknown/invalid/tampered (R10)
- [x] `tests/service/test_store.py` — 9 tests: all shipped fixtures load, records + external bytes round-trip, latest-version ordering, unknown ref / invalid record / tampered marker / missing-records all fail closed

## A-PR2 · orchestration façade (DSC-71)
Design note: a **live** run needs a `StageAdapter` + the macOS-gated native host, unavailable on
the universal path. So the façade is **read-only over committed evidence** (fixtures now, real run
outputs later — same record kinds). It builds a trusted `Handoff` and classifies the terminal
outcome from which records exist.
- [x] `service/orchestrator.py` — `load_analysis(path)` → `AnalysisView` with `outcome`
  (success/validation_failure/execution_failure/missing_inputs/running), `delivery_allowed` gate
  (R9), and accessors for report_draft / quantity_result / evaluation_result / proposal / submission;
  surfaces mock provenance + notice; `allow_mock=False` blocks mock-as-real
- [x] `tests/service/test_orchestrator.py` — 9 tests: all 5 fixtures classify correctly;
  success→report+orders+delivery_allowed; validation/execution failure→no orders, not delivery_allowed (R9);
  missing_inputs→pre-execution, proposal still readable; approved_execution→running; mock-as-real rejected

## A-PR3 · record → view translation (DSC-72)
- [x] `service/views.py` — `submission`→`Analysis`/`DataFile[]` (roles map §2.1 incl. `dictionary`); `evaluation_result`→`ModelResult[]`/`ModelRun`/`recommendedId` (baseline always shown, frozen=recommended; metrics mapped faithfully, not fabricated); `quantity_result`→`OrderLine[]`+exceptions (authoritative qty R5, exception distinct state R6); `report_draft`→summary/claims/findings; `esc()`/`safe_url()` escape text + http/https only (R11)
- [x] `tests/service/test_views.py` — 11 tests: roles incl. dictionary (R1); baseline present + single recommended (R3/R4); scores mapped not invented; authoritative order qty (R5); exceptions distinct (R6); failures carry no orders (R9); escaping + link safety (R11)
- note: proposal→`Readiness[]` deferred to A-PR5 (readiness is assembled at the API layer from proposal gaps alongside the intake endpoints)

## A-PR4 · server-side derived fields (DSC-73)
- [ ] `service/derive.py` — `coverWeeks`; flags+priority ≤2/+N (§4.3); supplier aggregate minimums+status+top-up (§4.2)
- [ ] `tests/service/test_derive.py` — §4.11 Ex 2, 3, 6 pass; client-supplied flag/cover ignored (R7, R8, R10)

## A-PR5 · HTTP API: intake arc (DSC-74)
- [ ] `service/api/` — `POST /analyses`, `POST/PATCH/DELETE …/files`, `GET …/readiness`, `POST …/approve-task`; deny-by-default auth stub (R10)
- [ ] propose minimal web framework via DSC-3 owner (don't add silently)
- [ ] `tests/service/test_api_intake.py` — full intake arc drives real `receive_submission`→`present_proposal`→`record_approval`→`start`; unauthorised denied

## A-PR6 · HTTP API: run/report/orders/export (DSC-75)
- [ ] `GET …/model-run`, `POST …/report`, `GET …/report/{tab}`, `GET …/order-lines` (filter/sort/group/paginate + group totals R13), `GET …/export.csv` (caller-scoped R10); report gated on `delivery_allowed` (R9)
- [ ] `tests/service/test_api_report.py` — §4.11 Ex 4 + Ex 10; pagination/group totals; CSV scope

## A-PR7 · run-progress events (DSC-76)
- [ ] `service/events.py` — progress/done channel; completion recorded even if nobody connected (R12)
- [ ] `tests/service/test_events.py` — §4.11 Ex 8

## A-PR8 · e2e happy path + demo runner (DSC-77)
- [ ] `tests/service/test_e2e_happy_path.py` — full spec §4 slice via the API
- [ ] `service/demo.py` — fixture-wired entrypoint for the demo/frontend
- [ ] all spec §6 acceptance items green
