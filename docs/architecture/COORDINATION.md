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
| Concrete schema version, compatibility and validated example set | DSC-24 | Exact `0.1.0-draft.3` development snapshot at `dd3e0dd` ACKed by DSC-3 and actual DSC-26; hashes and consumer instructions below |
| Integration subtree and semantic execution boundary | DSC-26 + DSC-3 | Exact paths and semantic responsibilities agreed; owner acknowledgment/discovery commit `455a215` reviewed by DSC-3 |
| Supported host/invocation/task transfer/artifact retrieval | DSC-26 | Managed-host probes exit 1; later normal-Terminal initialization/discovery succeeds but exposes no Data skills. Data invocation and analytical retrieval remain unverified; see evidence below |
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
- Actual DSC-26 worktree: `/private/tmp/suiroai-dsc26`, branch `codex/dsc-26-capability`, from the foundation commit; initial discovery `455a215`, Terminal/contract-ACK evidence `46404ad8e82b122ce796956c704747dbb48f350a`.
- The architecture branch does not merge either owner's implementation. Inspect their named branch/worktree for actual files; a path reservation is not an artifact present in this checkout. Other sessions' push authorization remains with those sessions.

## Actual DSC-26 discovery evidence and boundary agreement

DSC-3 reviewed commit `455a215` at `/private/tmp/suiroai-dsc26`, including `docs/integration/DISCOVERY.md`, `OWNERSHIP_ACK.md`, `PROBE_RECIPE.md` and `evidence/integration/discovery-2026-10-17/`. Saved-record checksums and byte identity with observed probe records passed. The ownership and semantic boundary are agreed; the invocation transport is not verified.

Codex CLI `0.163.0` app-server exited with code 1 before responding to initialization in the current managed host. The default attempt failed initializing SQLite state; retrying with writable SQLite state returned “Operation not permitted” without identifying the failing operation. Neither attempt reached skill discovery, Data attachment, a thread/turn, analytical execution, artifact retrieval or cancellation. This is not evidence of missing Data, authentication failure, model failure or universal lack of support. The owner correctly supplies discovery evidence and a candidate mechanism, not a fabricated adapter or analytical success.

Subsequent user-run normal-Terminal evidence is at `/private/tmp/suiroai-dsc26/docs/integration/TERMINAL_DISCOVERY.md` and `evidence/integration/terminal-discovery-2026-10-17/host-check.json`, committed by that owner in `46404ad8e82b122ce796956c704747dbb48f350a`. Its observed timestamp is `2026-10-17T19:07:00.192552+00:00`; the unmodified report SHA-256 is `22e89faf31afb3b118efdd5426d9dce4ddda0ae09fabc904e9a9869de24e678d`. DSC-3 independently checked initialization/discovery success, 13 returned skills, zero Data entries and no model turn. No thread/model turn or customer analysis began. Account-level installation claims are separate from this actual CLI response.

Current unblock: resolve supported Data exposure/activation in the actual executing host, then execute a bounded explicitly synthetic probe and return genuine code/output/artifacts plus version/failure/limit evidence. Parent checkpoint and development-context separation behavior still need proof. Capability discovery is distinct from a customer-approved task. The Terminal success narrows the earlier managed-host blocker and does not establish Data execution.

## DSC-24 snapshot review status

The actual owner's initial draft.1 schema SHA-256 was `cdcddc358a515b8b6a9546f540ac399de94f9de7047aa5957bc5d2fb577992ac`; it was not released. DSC-3 requested exact holdout binding, parent-veto enforcement, independently checked immutable candidate quantities, exception/name fidelity, agent-owned treatment resolution under the same task, disclosed synthetic-zero assumptions and honest standalone discovery. DSC-26 requested exact stage permission/attempt/input/budget/deadline/namespace and outcome-specific evidence. DSC-24 implemented the coordinated corrections without other owners editing its files.

**Agreed MVP development interface:** `0.1.0-draft.3`, code/example commit `dd3e0dda1b759ebe5439e78e8cf10e3374eb700b`, owner release/acknowledgment commit `487a8dc9aedd3b4de34efe9d76f2eec94d58d2f8` on local branch `codex/dsc-24-contracts`. The documentation-only release preserves all seven pinned file hashes and sets status `agreed_for_parallel_mvp_development`.

| Pinned artifact | SHA-256 / path |
| --- | --- |
| JSON Schema | `1d4615cf03d571d3ba9cc6df34e5848b109918d3b0274b7007abc8ce1544ed46` — `src/suiroai/contracts/schema/retail-contract.schema.json` |
| Semantic validator | `aecca19351e368e982ef014639c3f83120064fe1c480109fb41d3c9e9129368a` — `src/suiroai/contracts/validation.py` |
| Full schema/validator/five-example hash index | `docs/contracts/SNAPSHOT.json` in that commit; all seven indexed hashes independently verified by DSC-3 |
| Examples | `examples/contracts/v0.1.0/{approved_execution,missing_inputs,successful_analysis,validation_failed,execution_failed}.json`; every chain is mock |

DSC-3 explicitly ACKed that exact snapshot after three focused read-only reviews, an independent 77-test run under locked `jsonschema 4.26.0`, and regression counterexamples rejecting holdout substitution, parent veto bypass, absent final permission, false independent evidence and altered report names. Actual DSC-26 session `01a14ad0-60c2-7c43-bdfa-3ce602d3794e` independently ACKed structural compatibility at the same commit/schema hash after its 77-test/hash review; its acknowledgment is recorded in its `docs/integration/CONTRACT_REVIEW.md`. DSC-24 recorded both exact ACKs in release commit `487a8dc`; no acknowledgment is inferred from silence.

Consumers in this shared local repository may create an isolated branch/worktree from owner release commit `487a8dc9aedd3b4de34efe9d76f2eec94d58d2f8` and build only their owned component against its examples. The architecture branch does not merge the contract code or publish that owner's branch. Use the exact commit/hash set. Substantive schema/meaning changes require a coordinated revision and affected-consumer updates. Unresolved actual target interpretation, thresholds, genuine parent enforcement, real source availability and native execution remain genuine implementation prerequisites; fixtures do not decide them.

## Foundation verification

`uv lock` and `uv sync --locked` passed, including editable package build. Application and JSON Schema validator imports passed. `python -m build --no-isolation` using the cached build backend produced both source distribution and wheel; wheel inspection confirmed the package root is included and raw data/DSCraft are excluded. `git diff --check` and local Markdown-link checks passed. The `uv build` frontend itself panicked in macOS system-configuration initialization in this managed environment; the alternate standard Python build passed. None of these checks is analytical or integration acceptance.

## Questions for the actual owners

DSC-24: layout, snapshot and revision agreement are complete for development. Preserve the pinned release and identify any future material business arithmetic/acceptance decisions through versioned policies. Do not edit package manifests; send dependency requests to DSC-3.

DSC-26: paths are acknowledged. Supply supported host/invocation evidence and the actual capability boundary, including restricted development inputs, holdout release, checkpoint/resume, result identity and errors. If no supported mechanism exists, state that blocker. Do not define a new shared wire contract or change manifests independently.

Evidence-backed acknowledgments should cite the owner's exact artifact path/version or message. DSC-3 will update this ledger after receiving them; an issue description, read-only review or lack of objection is not acknowledgment.

## Safe parallelism now

Architecture and contract/capability discovery may proceed independently. No other component implementation is performed by DSC-3. Layout acknowledgment now permits the agreed minimal foundation; consumer work is unlocked by the reviewed interface examples, not by a mocked upstream success. Actual execution/acceptance waits for native blockers and real artifacts. The user-authorized Git backup is distinct from merging, deploying or marking any Linear issue complete.
