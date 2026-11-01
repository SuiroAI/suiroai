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

## A-PR2 · orchestration driver (DSC-71)
- [ ] `service/orchestrator.py` — load a contract fixture bundle into the store; advance workflow stages; expose state + `checkpoint()`; surface mock provenance
- [ ] `tests/service/test_orchestrator.py` — `successful_analysis` → report+quantity; `missing_inputs` → readiness gaps (R2); `validation_failed`/`execution_failed` → failure report, no orders (R9)

## A-PR3 · record → view translation (DSC-72)
- [ ] `service/views.py` — `submission`→`Analysis`/`DataFile[]` (roles map §2.1 incl. `dictionary`); gaps→`Readiness[]`; `evaluation_result`→`ModelResult[]`/`ModelRun`/`recommendedId`; `quantity_result`→`OrderLine[]`+exceptions; `report_draft`→summary/data tabs; escape text, http/https only (R11)
- [ ] `tests/service/test_views.py` — fixtures round-trip without loss/fabrication; metric labels match §4.7 (R3); recommended rule (R4); exceptions as distinct state (R6)

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
