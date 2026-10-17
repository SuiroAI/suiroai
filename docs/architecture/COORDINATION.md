# DSC-3 coordination and integration prerequisites

October 17, 2026 · architecture decision revision 0.1.0.

## Published proposal

- Selected application project and Git root: `suiroai/`, with `pyproject.toml`, import package `src/suiroai/`, Python `>=3.11`. Canonical architecture docs are `suiroai/docs/architecture/`; workspace `docs/mvp/` files point here.
- Exclusive paths: [OWNERSHIP.md](OWNERSHIP.md). Workflow and semantic interfaces: [ARCHITECTURE.md](ARCHITECTURE.md).
- DSC-3's three subagents performed read-only design/evidence review. They are not the agents assigned to implement DSC-24 or DSC-26 and cannot provide those owners' agreement.
- Actual DSC-24/DSC-26 owners acknowledged layout/path reservations through the Codex cross-session coordination channel. No external Linear/Miro messages or edits are performed.

## Owner acknowledgment ledger

| Required agreement | Owner | Current evidence/status |
| --- | --- | --- |
| Target package and exclusive contract paths | DSC-24 + DSC-3 | ACK received from actual DSC-24 owner; JSON Schema Draft 2020-12 with `jsonschema>=4.18,<5`, Python >=3.11 |
| Concrete schema version, compatibility and validated example set | DSC-24 | Owner preparing `0.1.0-draft.1` in staging, examples path `suiroai/examples/contracts/v0.1.0/`; snapshot review pending |
| Integration subtree and semantic execution boundary | DSC-26 + DSC-3 | Exact paths and semantic responsibilities agreed; owner acknowledgment/discovery commit `455a215` reviewed by DSC-3 |
| Supported host/invocation/task transfer/artifact retrieval | DSC-26 | Real probes exit 1 before initialization; no analytical invocation demonstrated. Current managed-host startup blocks verification; see evidence below |
| Development/holdout isolation and parent checkpoints | DSC-26 with DSC-10/27/28 | Required by architecture; supported mechanism unverified |
| Parent transition/recovery cap and persistence mechanism | DSC-10 | Exclusive ownership reserved; finite policy must be declared before execution |
| Shared dependencies/config/lock changes | DSC-3 | Foundation released after owner ACKs; sole dependency request `jsonschema>=4.18,<5` accepted; DSC-3 owns lock/build checks |
| Git branch and remote backup | DSC-3/user | New private repository `https://github.com/SuiroAI/suiroai`; `codex/dsc-3-mvp-architecture` pushed for user-authorized backup. DSCraft is excluded; no merge/deploy/issue change |

## Actual acknowledgment evidence

- DSC-24 session `01a14ad0-5384-7bb3-bc03-afd35c43ea2f`: “ACK exact application layout and exclusive DSC-24 paths” for `src/suiroai/contracts/`, `tests/contracts/`, `examples/contracts/v0.1.0/`, `docs/contracts/`. Owner requested `jsonschema>=4.18,<5`, agreed not to edit manifests, and identified initial internal version `0.1.0-draft.1` pending DSC-3/26 review. DSC-3 acknowledged the reservation and dependency.
- DSC-26 session `01a14ad0-60c2-7c43-bdfa-3ce602d3794e`: “ACK exact reserved integration source/tests/docs/evidence paths; no shared edits.” Owner requested an application-local Git base for an isolated worktree. DSC-3 confirmed the application-local boundary and will supply the exact foundation commit.
- An earlier workspace-root Git proposal was superseded by the application-local boundary before Git initialization. Component paths remain the same relative to `suiroai/`; raw data and DSCraft are outside this repository. All three sessions must branch from the published base and edit only owned files.

## Git base and local component worktrees

Foundation commit: `7e1dbb531a20f0ad4e4f82ec5764177e87550b3c`, application root `/Users/ceverson/Development/SuiroAI/suiroai`, branch `codex/dsc-3-mvp-architecture`.

- Actual DSC-24 worktree: `/private/tmp/suiroai-dsc24`, branch `codex/dsc-24-contracts`, from the foundation commit.
- Actual DSC-26 worktree: `/private/tmp/suiroai-dsc26`, branch `codex/dsc-26-capability`, from the foundation commit; discovery commit `455a215`.
- The architecture branch does not merge either owner's implementation. Inspect their named branch/worktree for actual files; a path reservation is not an artifact present in this checkout. Other sessions' push authorization remains with those sessions.

## Actual DSC-26 discovery evidence and boundary agreement

DSC-3 reviewed commit `455a215` at `/private/tmp/suiroai-dsc26`, including `docs/integration/DISCOVERY.md`, `OWNERSHIP_ACK.md`, `PROBE_RECIPE.md` and `evidence/integration/discovery-2026-10-17/`. Saved-record checksums and byte identity with observed probe records passed. The ownership and semantic boundary are agreed; the invocation transport is not verified.

Codex CLI `0.163.0` app-server exited with code 1 before responding to initialization in the current managed host. The default attempt failed initializing SQLite state; retrying with writable SQLite state returned “Operation not permitted” without identifying the failing operation. Neither attempt reached skill discovery, Data attachment, a thread/turn, analytical execution, artifact retrieval or cancellation. This is not evidence of missing Data, authentication failure, model failure or universal lack of support. The owner correctly supplies discovery evidence and a candidate mechanism, not a fabricated adapter or analytical success.

Unblock: an authorized supported host must initialize, discover/apply Data, execute a bounded explicitly synthetic probe and return genuine code/output/artifacts plus version/failure/limit evidence. Parent checkpoint and development-context separation behavior still need proof. Capability discovery is distinct from a customer-approved task.

## DSC-24 snapshot review status

The actual owner's `0.1.0-draft.1` snapshot initially had schema SHA-256 `cdcddc358a515b8b6a9546f540ac399de94f9de7047aa5957bc5d2fb577992ac`. It includes sixteen record kinds and five clearly mock chains. DSC-3 requested changes before snapshot agreement: exact reserved-holdout binding; honoring intermediate parent vetoes; independent check-to-candidate/version bindings; retaining quantity exceptions in the report; versioned agent-owned treatment resolution under the same approved task; disclosed defensible scenario assumptions; honest standalone engineering discovery; and supported product-name mapping. Those requests go to DSC-24 only. Its schema/audit/mock tests do not establish genuine workflow acceptance. Final agreement must cite the revised immutable snapshot and review outcome.

## Foundation verification

`uv lock` and `uv sync --locked` passed, including editable package build. Application and JSON Schema validator imports passed. `python -m build --no-isolation` using the cached build backend produced both source distribution and wheel; wheel inspection confirmed the package root is included and raw data/DSCraft are excluded. `git diff --check` and local Markdown-link checks passed. The `uv build` frontend itself panicked in macOS system-configuration initialization in this managed environment; the alternate standard Python build passed. None of these checks is analytical or integration acceptance.

## Questions for the actual owners

DSC-24: paths are acknowledged. Publish the concrete schema/compatibility snapshot and mutually consistent versioned examples for the handoffs/branches in the architecture. Identify any material business arithmetic/acceptance decisions still unresolved. Do not edit package manifests; send dependency requests to DSC-3.

DSC-26: paths are acknowledged. Supply supported host/invocation evidence and the actual capability boundary, including restricted development inputs, holdout release, checkpoint/resume, result identity and errors. If no supported mechanism exists, state that blocker. Do not define a new shared wire contract or change manifests independently.

Evidence-backed acknowledgments should cite the owner's exact artifact path/version or message. DSC-3 will update this ledger after receiving them; an issue description, read-only review or lack of objection is not acknowledgment.

## Safe parallelism now

Architecture and contract/capability discovery may proceed independently. No other component implementation is performed by DSC-3. Layout acknowledgment now permits the agreed minimal foundation; consumer work is unlocked by the reviewed interface examples, not by a mocked upstream success. Actual execution/acceptance waits for native blockers and real artifacts. The user-authorized Git backup is distinct from merging, deploying or marking any Linear issue complete.
