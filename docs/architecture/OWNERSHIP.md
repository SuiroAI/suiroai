# Retail MVP ownership map — DSC-3

Architecture decision revision: 0.1.0, October 17, 2026. Scope: the single M01 retail restocking case only.

This map was published before DSC-3 wrote application infrastructure. The selected application location is `suiroai/`, an independent Python project and Git repository with import package `suiroai` under `suiroai/src/`. The workspace root is not a Git repository. `dscraft/` is a separate repository and is read-only for this assignment. Canonical architecture documents live under `suiroai/docs/architecture/`; workspace `docs/mvp/` files are pointers.

## Coordination status

The actual DSC-24 and DSC-26 session owners acknowledged the application layout and their exact reserved paths through cross-session messages. [COORDINATION.md](COORDINATION.md) records the session identities and acknowledgment evidence. The minimal foundation may now be written by DSC-3; concrete contract snapshot approval and real execution-boundary evidence remain separate waits. DSC-3's review subagents do not replace either actual owner. Consumers wait for the agreed DSC-24 interface snapshot, but not for every upstream implementation.

## Exclusive write ownership

All paths are workspace-relative. An owner may create files only in its listed area. A nonexistent directory is reserved, not an implemented component.

| Owner | Exact owned files/directories | Responsibility |
| --- | --- | --- |
| DSC-3 | `suiroai/docs/architecture/`; workspace pointer files `docs/mvp/ARCHITECTURE.md`, `docs/mvp/OWNERSHIP.md`, `docs/mvp/COORDINATION.md`; `suiroai/README.md`, `suiroai/pyproject.toml`, `suiroai/uv.lock`, `suiroai/.gitignore`, `suiroai/src/suiroai/__init__.py` | Architecture, application package foundation, manifest/lock and shared tooling configuration; application-local Git base and user-authorized backup branch |
| DSC-24 | `suiroai/src/suiroai/contracts/`, `suiroai/tests/contracts/`, `suiroai/examples/contracts/v0.1.0/`, `suiroai/docs/contracts/` | Sole owner of shared schemas, serialization, compatibility rules and versioned example packets, including the evidence-record type |
| DSC-10 | `suiroai/src/suiroai/parent/`, `suiroai/tests/parent/`, `suiroai/docs/parent/` | Sole owner of state, proposal/approval binding, transitions, checkpoint decisions, bounded recovery, persistence/resume and final response authorization |
| DSC-25 | `suiroai/src/suiroai/intake/`, `suiroai/tests/intake/`, `suiroai/docs/intake/` | File/request receipt, read-only inspection, proposal/gap explanation, sign-off conversation; no joining/preparation or parent transitions |
| DSC-26 | `suiroai/src/suiroai/integration/`, `suiroai/tests/integration/`, `suiroai/docs/integration/`, `suiroai/evidence/integration/` | Supported Codex/Data boundary, capability probe, transport/file/result handling, inspectable errors and real integration evidence |
| DSC-27 | `suiroai/src/suiroai/preparation/`, `suiroai/tests/preparation/`, `suiroai/docs/preparation/` | Post-approval cleaning, joins, lineage, temporal partitioning, EDA and initial features |
| DSC-28 | `suiroai/src/suiroai/modeling/`, `suiroai/tests/modeling/`, `suiroai/docs/modeling/` | Initial baseline gate, LLM feature definitions/materialization validation, bounded comparison, frozen artifacts, final evaluation and defect-recheck evidence |
| DSC-29 | `suiroai/src/suiroai/replenishment/`, `suiroai/tests/replenishment/`, `suiroai/docs/replenishment/`; separately `suiroai/src/suiroai/reporting/`, `suiroai/tests/reporting/`, `suiroai/docs/reporting/` | Numerical order calculation versus evidence-linked customer narrative; report rendering never recalculates quantities |
| DSC-30 | `suiroai/src/suiroai/verification/`, `suiroai/tests/verification/`, `suiroai/docs/verification/` | Independent quantity and claim verification, success/failure draft verification and parent-authorized delivery |
| DSC-56 | `suiroai/tests/acceptance/`, `suiroai/docs/acceptance/`, `suiroai/evidence/acceptance/` | Fixed requirement-to-evidence audit, named verifier decisions; no schema or parent changes |
| DSC-31 | `suiroai/docs/demo/`, `suiroai/evidence/demo/` | Real recording instructions, artifact index and capture evidence; no staged/mock recording represented as execution |
| DSC-9 reviewer | `suiroai/docs/completion/`, `suiroai/evidence/completion/` | MVP completion checklist and named acceptance review after genuine child artifacts and recording |

## Shared changes and artifacts

- Route all dependency, manifest, lockfile, common test configuration and CI requests through DSC-3. Component owners supply package/version/extra and reason; they do not independently edit shared infrastructure. No root-wide `conftest.py` or convenience cross-component helper is introduced without this owner.
- Route every shared-schema change through DSC-24. Component-local fixtures may live in the component's tests but must cite the agreed contract version and carry an explicit mock/example designation. No consumer forks a shared schema.
- Route all workflow/checkpoint/retry changes through DSC-10. Workers return artifacts and outcomes; they do not advance state or approve their own delivery.
- Generated run artifacts are reserved under `suiroai/artifacts/<task-id>/<run-id>/`, excluded from ordinary source commits. The approved contract names each stage's output namespace; one producer per artifact and immutable version/hash references prevent cross-stage overwrites. This is an output location, not a new storage service/runtime.
- Source datasets under `data/retail_mvp/sales_2022_2025/` stay immutable. `dscraft/`, `docs/MVP_ROLE_BASED_PROMPTS.md`, existing `output/`, archived 2016 cases and Miro stay outside these write allocations.
- Git backup must use the user-confirmed closed-source application repository/branch, never the separate public DSCraft remote. Stage explicit owned paths only; do not absorb other sessions' uncommitted work, raw customer data, credentials or generated run artifacts.

## Release of parallel work

1. Layout/path acknowledgment is received from actual DSC-24 and DSC-26 sessions; exact evidence is recorded in [COORDINATION.md](COORDINATION.md). Each role uses an isolated Git worktree/branch from the DSC-3 foundation commit, retaining the same repository-relative paths. Do not write into another role's checkout.
2. DSC-24 publishes a versioned, validated interface example set and compatibility rule. DSC-3 reviews that it covers every handoff in [ARCHITECTURE.md](ARCHITECTURE.md). Until then the proposed `v0.1.0` directory is a reservation, not a usable schema snapshot.
3. DSC-3 writes only the agreed foundation; each role builds its own consumer against the agreed snapshot. DSC-24's initial draft version `0.1.0-draft.1` is not stable until owner review. Changing a shared file requires its owner's update.
4. Mock consumer checks allow development only. Actual integration acceptance waits for DSC-26 capability/execution evidence and genuine upstream artifacts; native Linear blockers and named review remain in force. This assignment does not close DSC-3's broader V1 architecture.
