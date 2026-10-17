# DSC-24 ownership and snapshot coordination

Snapshot: `0.1.0-draft.3`. State: agreed and released as the pinned MVP development interface by DSC-24, DSC-3 and DSC-26. Architecture path ownership has been mutually acknowledged. This record separates that acknowledgement from consumer acceptance of the definitions.

## Owners and proposed boundaries

DSC-24 is the single owner of shared task/data contracts and representative interface examples. DSC-3 owns architecture/layout agreement; DSC-10 owns parent/orchestration; DSC-26 supplies the related discovery/integration coordination. Other components consume shared definitions and request changes through DSC-24, coordinated with DSC-3. No consumer should independently edit the same shared files.

DSC-3 reserved the following exact application paths and DSC-24 accepted them. DSC-3 supplied foundation commit `7e1dbb531a20f0ad4e4f82ec5764177e87550b3c`; DSC-24 created `/private/tmp/suiroai-dsc24` on `codex/dsc-24-contracts` and writes only these paths:

| Reserved path | DSC-24 responsibility | Status |
| --- | --- | --- |
| `suiroai/src/suiroai/contracts/` | Concrete versioned definitions and source/evidence interface support | Mutual path and exact snapshot acknowledgement |
| `suiroai/tests/contracts/` | Meaningful contract conformance and cross-binding checks | Mutual path acknowledgement |
| `suiroai/examples/contracts/v0.1.0/` | Clearly marked component fixtures | Mutual path acknowledgement; folder name does not promote draft version |
| `suiroai/docs/contracts/` | Field meanings, source reconciliation, semantics and snapshot/revision record | Mutual path acknowledgement |

No `dscraft/` public interfaces are changed by this draft. The reviewable draft lives in `/private/tmp/suiroai-dsc24`; temporary preparation files are not the consumer destination. Canonical architecture documents are `suiroai/docs/architecture/OWNERSHIP.md`, `ARCHITECTURE.md` and `COORDINATION.md`; root `docs/mvp/` documents are pointers. DSC-3 accepted the proposed `jsonschema>=4.18,<5` application dependency; that acceptance does not establish analytical runtime capability.

## Coordination evidence and remaining waits

The user authorized coordination as needed and stated that DSC-3 and DSC-26 are working in other agent sessions, with coordination expected in GitHub. Initial read-only connector discovery found the authenticated account `gr3enarr0w` and the public repository [SuiroAI/dscraft](https://github.com/SuiroAI/dscraft), whose README describes the separate DSCraft library.

Scoped SuiroAI issue/PR searches for DSC references, repository issue searches and code searches for DSC-24/ownership returned no accessible relevant records. A direct lookup of `SuiroAI/suiroai` returned 404; this does not prove that no private application repository exists. The connected GitHub installation inventory exposed only the personal `gr3enarr0w` account and no SuiroAI installation. These initial access limits do not negate the later direct-session ownership acknowledgement.

Subsequent shared architecture files and direct Codex session coordination established the reserved paths above. The DSC-3 coordination thread is `01a14ad0-4645-7661-b396-a295d232196e`; the parent sent DSC-24's path acknowledgement and dependency request and received DSC-3 acknowledgement, including the instruction to wait for its base and use an isolated worktree. DSC-26 was contacted on thread `01a14ad0-60c2-7c43-bdfa-3ce602d3794e` with the acknowledged paths and a request for snapshot review/agreement. Both actual owners subsequently supplied explicit exact snapshot acknowledgement, recorded below.

No external issue comment, status change or repository publication has been made by this documentation task. An inaccessible linked source must not be described as read. The parent records linked Linear/source access and any subsequent publication destination separately.

## Definition readiness

The version/binding envelope, seventeen message kinds implementing the ten interface concepts, observed-versus-synthetic provenance, temporal separation, source completeness conditions, independent verification and terminal outcome distinctions are agreed for independent consumer implementation against the pinned snapshot. Consumers may use the clearly marked mocks; they must not claim integration acceptance or completed analytical implementation.

Release gates:

1. Completed: received the foundation and isolated-worktree handoff; allocated paths are preserved.
2. Completed: both actual owners acknowledged the exact schema, validator, example hashes and boundary semantics.
3. Completed locally on the isolated contract branch: immutable snapshot, definitions, examples, reconciliation and unresolved semantics. Remote publication is a separate authorized action.
4. Record affected consumers, their accepted version and any implementation blocks explicitly. Mock test success does not remove genuine upstream dependencies or justify issue closure.

The current draft deliberately leaves real target semantics and measured acceptance thresholds unresolved. Hypothetical fixture values are not customer business decisions. Agreement on a structural interface does not resolve these data semantics or authorize analytical execution.

## Coordinated revision rule

Do not mutate an agreed snapshot in place. A change requires a new contract revision, a reason and compatibility/semantic impact record, affected consumer identification, and coordinated owner acknowledgement plus affected consumer approval/update before shared dependence. Existing artifacts retain their original schema/version/hash bindings; migration or replacement artifacts carry explicit new versions.

A schema-only repair that preserves the approved business task and input meaning does not itself require customer reapproval. Changes to material business facts, target/scope assumptions, source input semantics or the proposed output return to proposal formation and renewed customer signoff against the new task/input/proposal binding. Approval can never be carried forward merely because an artifact ID or file path stayed the same.

Do not merge, deploy, change issue status, or count contract/fixture validation as an implemented analytical pipeline. Publication and external updates remain subject to the user's actual authorization and the verified repository destination.

## Snapshot review and revision

Draft.1 (`cdcddc358a515b8b6a9546f540ac399de94f9de7047aa5957bc5d2fb577992ac`) was reviewed by DSC-3 and DSC-26 and was not released. Draft.2 fixes exact holdout binding, dependent parent permissions, acyclic independently checked candidate/approved quantities, report exception preservation, pending statistical policy resolution, explicit synthetic-zero assumptions, display-name fidelity, and stage requests with exact permission/attempt/input/budget/namespace bindings and outcome-specific evidence. Standalone engineering discovery remains separate from customer execution contracts.

Current schema version: `0.1.0-draft.3`; byte SHA-256: `1d4615cf03d571d3ba9cc6df34e5848b109918d3b0274b7007abc8ce1544ed46`. Five mock bundles and 77 regression tests pass; actual local source reconciliation has 41 passed checks and zero failures. These are not analytical-pipeline acceptance. Both owners supplied exact structural acknowledgement as recorded below.

Draft.2 review identified a final budget representation gap: exhausted unrelated resources must be representable as zero. Draft.3 separates nonnegative remaining budgets from whole-run capacities and checks required stage resources before dispatch. The parent remains responsible for authoritative counters and actual enforcement.

## Exact owner agreement and lane release

On October 17, 2026, actual DSC-3 owner thread `01a14ad0-4645-7661-b396-a295d232196e` explicitly acknowledged commit `dd3e0dda1b759ebe5439e78e8cf10e3374eb700b`, schema version `0.1.0-draft.3`, schema SHA-256 `1d4615cf03d571d3ba9cc6df34e5848b109918d3b0274b7007abc8ce1544ed46`, and validator SHA-256 `aecca19351e368e982ef014639c3f83120064fe1c480109fb41d3c9e9129368a`. DSC-3 independently passed 77 tests under locked jsonschema 4.26 and verified all seven snapshot file hashes. Focused reviewers and rehashed counterexamples confirmed the requested fixes.

Actual DSC-26 owner thread `01a14ad0-60c2-7c43-bdfa-3ce602d3794e` explicitly acknowledged the same committed draft.3/schema digest after independently passing 77 tests and verifying all seven file hashes. Its review records acceptance of stage permission/attempt bindings, released inputs, nonnegative remainders and predispatch checks, actionable gaps/failure evidence, and separate engineering discovery. Its owner-authored review is `docs/integration/CONTRACT_REVIEW.md` in `/private/tmp/suiroai-dsc26`.

DSC-24 now releases the definitions and five mock examples for parallel lanes DSC-10, DSC-25, DSC-26, DSC-27, DSC-28, DSC-29, DSC-30, DSC-56, DSC-31 and DSC-9, pinned to the seven hashes in SNAPSHOT.json. This is agreement on the development interface, not proof that any consumer exists or has integrated it. Consumer owners must import/validate the shared schema and request coordinated revisions instead of forking it. Later changes require explicit version/compatibility impact and affected consumer updates. Material task/input changes also require a new proposal and approval.

No analytical/runtime acceptance is granted. DSC-26's later user-run Terminal initialization and skill listing succeeded, but Data was absent from that listing despite its account plugin being reported installed/enabled. CLI exposure and genuine Data execution remain unresolved. Real task semantics, model thresholds and source completeness are not resolved by interface agreement. Native issue blockers and statuses remain unchanged.

This acknowledgement record changes documentation only. The agreed schema, validator and example file hashes remain exactly those of dd3e0dd.
