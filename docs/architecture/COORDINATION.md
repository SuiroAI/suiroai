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
| Integration subtree and semantic execution boundary | DSC-26 + DSC-3 | Exact integration source/tests/docs/evidence paths ACKed; actual supported mechanism/evidence pending |
| Supported host/invocation/task transfer/artifact retrieval | DSC-26 | No demonstrated invocation in inspected issue/comments; must consume actual owner evidence |
| Development/holdout isolation and parent checkpoints | DSC-26 with DSC-10/27/28 | Required by architecture; supported mechanism unverified |
| Parent transition/recovery cap and persistence mechanism | DSC-10 | Exclusive ownership reserved; finite policy must be declared before execution |
| Shared dependencies/config/lock changes | DSC-3 | Foundation released after owner ACKs; sole dependency request `jsonschema>=4.18,<5` accepted; DSC-3 owns lock/build checks |
| Git branch and remote backup | DSC-3/user | User requests new branch and backup. Application-local Git base selected so roles can create isolated worktrees; private origin still unknown. Only discovered remote is separate public `SuiroAI/dscraft`; do not push application there |

## Actual acknowledgment evidence

- DSC-24 session `01a14ad0-5384-7bb3-bc03-afd35c43ea2f`: “ACK exact application layout and exclusive DSC-24 paths” for `src/suiroai/contracts/`, `tests/contracts/`, `examples/contracts/v0.1.0/`, `docs/contracts/`. Owner requested `jsonschema>=4.18,<5`, agreed not to edit manifests, and identified initial internal version `0.1.0-draft.1` pending DSC-3/26 review. DSC-3 acknowledged the reservation and dependency.
- DSC-26 session `01a14ad0-60c2-7c43-bdfa-3ce602d3794e`: “ACK exact reserved integration source/tests/docs/evidence paths; no shared edits.” Owner requested an application-local Git base for an isolated worktree. DSC-3 confirmed the application-local boundary and will supply the exact foundation commit.
- An earlier workspace-root Git proposal was superseded by the application-local boundary before Git initialization. Component paths remain the same relative to `suiroai/`; raw data and DSCraft are outside this repository. All three sessions must branch from the published base and edit only owned files.

## Questions for the actual owners

DSC-24: paths are acknowledged. Publish the concrete schema/compatibility snapshot and mutually consistent versioned examples for the handoffs/branches in the architecture. Identify any material business arithmetic/acceptance decisions still unresolved. Do not edit package manifests; send dependency requests to DSC-3.

DSC-26: paths are acknowledged. Supply supported host/invocation evidence and the actual capability boundary, including restricted development inputs, holdout release, checkpoint/resume, result identity and errors. If no supported mechanism exists, state that blocker. Do not define a new shared wire contract or change manifests independently.

Evidence-backed acknowledgments should cite the owner's exact artifact path/version or message. DSC-3 will update this ledger after receiving them; an issue description, read-only review or lack of objection is not acknowledgment.

## Safe parallelism now

Architecture and contract/capability discovery may proceed independently. No other component implementation is performed by DSC-3. Layout acknowledgment now permits the agreed minimal foundation; consumer work is unlocked by the reviewed interface examples, not by a mocked upstream success. Actual execution/acceptance waits for native blockers and real artifacts. The user-authorized Git backup is distinct from merging, deploying or marking any Linear issue complete.
