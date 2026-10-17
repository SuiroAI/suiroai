# DSC-26 supported-interface discovery

Revision 0.2.0 · 2026-10-17 · **Real bounded Codex/Data engineering invocation demonstrated; full adapter acceptance incomplete.**

The user's normal Terminal completed a real synthetic stage through Codex app-server `0.163.0`, with installed/enabled OpenAI Data `1.0.11` and the native Data plugin mention. The executing turn read Data's index and shared instructions, generated and executed Python, and returned verified artifact bytes. Independent review confirmed three rows, group totals `A=5`, `B=5`, total `10`, and unchanged engineering task/input/run bindings. See the [reviewed evidence](../../evidence/integration/native-stage-2026-10-17/review.json) and [probe history](SYNTHETIC_PROBE.md). No customer analysis ran.

The [draft.3 contract review](CONTRACT_REVIEW.md) records DSC-26's exact structural ACK. A narrow [adapter](ADAPTER.md) now consumes that snapshot and has mocked version/failure checks. Real native cancellation and timeout interruptions have been confirmed. A real syntax failure exposed a classifier defect; commit `ef8fcdb` fixes it, and offline replay of the unchanged native evidence identifies the actual failed command. The original incorrect `completed` adapter observation is preserved in the [failure review](../../evidence/integration/native-failures-2026-10-17/review.json), not rewritten as a successful original check. Customer dispatch fails closed until released-input-only native read isolation is demonstrated, and customer execution still requires DSC-25 approval plus DSC-10 permission. Metadata discovery used under-development `plugin/read`; the new transport does not depend on it. The observed model provider was `openai`; the intended LiteLLM gateway route was not verified.

Earlier managed-environment startup failures, Terminal skill-list omission and two probe request corrections remain historical evidence below. An absent `skills/list` entry did not establish remote Data unavailability; native remote retrieval and the later executing turn established the supported route in that Terminal context. No cached skill was registered as a replacement plugin.

## Historical managed-environment startup results

The installed Codex CLI reports `codex-cli 0.163.0`. Two initial engineering probes attempted the documented app-server stdio interface. Both child processes exited with code 1 before replying to `initialize`. Neither reached `skills/list`, `thread/start`, or `turn/start`. Those two probes ran no synthetic calculation or customer analysis and produced no analytical artifact.

| Probe | Actual observation | Evidence |
| --- | --- | --- |
| Default local configuration | Failed to initialize SQLite state under `/Users/ceverson/.codex` | [Unmodified record](../../evidence/integration/discovery-2026-10-17/appserver-default.json) |
| Writable SQLite state override | Exited with `Error: Operation not permitted (os error 1)` before any RPC reply | [Unmodified record](../../evidence/integration/discovery-2026-10-17/appserver-writable-state.json) |

The second launch used the documented `sqlite_home` configuration option, pointing to `/private/tmp/dsc26-host-state`. It retained the ordinary host configuration and authentication location. No credentials were copied or printed, no approval/sandbox policy was bypassed, and no plugin was installed or reconfigured. The second error does not identify its underlying failing operation; do not attribute it to authentication, Data, network access, or a specific host restriction without more evidence.

This is a startup blocker in the current managed environment. It is **not** evidence that Codex/Data is universally unsupported, that Data is missing, or that an analytical validation failed. A successful Python probe harness exit only means its observation was saved; the actual app-server child exit is 1.

## Supported candidate and evidence limits

Official OpenAI documentation describes app-server initialization, `skills/list`, explicit skill attachments in `turn/start`, persisted execution history, and `turn/interrupt`. These form a supported candidate for discovery and execution, subject to successful verification in the executing host. Plugin-management methods are described as under development; this assignment does not depend on inventing a Data endpoint or installing through those methods. [Codex App Server](https://learn.chatgpt.com/docs/app-server)

The current session exposes Data skills. Its installed manifest identifies **OpenAI Data**, package `data-analytics`, version `1.0.11`, with a skill directory and no execution MCP mapping. Data can guide code executed by a supported Codex host; a separate Data execution service is not a prerequisite. Local execution would count only with evidence that the actual host applied the Data skill. Merely reading a skill file during discovery, seeing its manifest, or running generic Python does not establish that chain.

The native task tools expose task creation/history, but their inspected schemas do not expose explicit Data binding, cancellation, or stage deadlines. They were inspected, not used to claim an alternate working adapter. No Code Interpreter substitution occurred.

The official environment-variable reference documents SQLite state relocation and config precedence. [Codex environment variables](https://learn.chatgpt.com/docs/config-file/environment-variables)

No Tavily tool or `tavily-research/SKILL.md` was available at its configured path in this environment. Research used official OpenAI pages instead; the Tavily workflow itself was not exercised. All observations are bounded to this host and date.

## Evidence index and version status

- [Inventory](../../evidence/integration/discovery-2026-10-17/inventory.json): host identity, installed plugin/skill byte hashes, worktree/base commit, engineering scope and absent customer bindings.
- [Observation checks](../../evidence/integration/discovery-2026-10-17/observation-checks.json): confirms both saved records preserve actual startup failure and zero analytical invocation. These checks do not pass integration acceptance.
- [Probe recipe](PROBE_RECIPE.md): commands, requests, deadline and evidence-capture procedure actually exercised.
- [Ownership acknowledgment](OWNERSHIP_ACK.md): agreement with DSC-3 and exclusive paths.
- [Reviewed native stage](../../evidence/integration/native-stage-2026-10-17/review.json): actual host/plugin/turn/command identities, artifact digests, 27 independent checks and scoped manual-review decision. Four small synthetic artifacts are retained alongside it; original raw evidence paths/digests are indexed without committing full skill text or agent reasoning.

The JSON observations are engineering records, **not instances of an invented shared execution/result/evidence schema**. DSC-24 remains the sole owner of that schema. There is no customer task/proposal/approval/source version because no customer stage was submitted. The successful synthetic turn demonstrates its engineering task/input/run binding passthrough. Mocked adapter tests exercise broader binding propagation and mismatch rejection; those are not real customer execution evidence.

## Adapter boundary after prerequisites clear

Consume DSC-24's agreed execution/result contract and the same task proposed in DSC-25 step 2 and approved in step 3. Require DSC-10 parent permission before any customer invocation. Transfer only the contract-authorized file references, actions, as-of context and limits; return outcomes and immutable evidence for parent checkpoint decisions. The adapter owns no intake, cleaning, feature definitions, modeling, restocking arithmetic, report content, parent transitions, retry decisions or final delivery authorization.

Before invoking a customer stage, independently check task/run/input/proposal/approval/assumption versions and file accessibility. The executing worker must receive only permitted development artifacts for feature generation and selection. Giving unrestricted December rows to a development turn is prohibited; a prompt telling it to ignore those rows is insufficient isolation. Final evaluation requires parent-authorized frozen references and holdout release. The November 30 forecast remains immutable.

On a verified host, retain actual thread/turn identifiers, outbound skill attachment, executable and plugin/skill identity, executed code/config and outputs, final status, and artifact bytes/digests. Validate version bindings and returned artifact identity independently. If history normalizes skill input, retain the accepted outbound request with retrieved execution items. Host turn completion alone does not pass an analytical checkpoint. Result text that claims a calculation ran does not substitute for code/output/artifact evidence.

Enforce a finite deadline and declared limits around the supported mechanism. Interruption must have an observed terminal outcome; an interrupt request alone does not prove cancellation. Never accept late artifacts as a current success, retry autonomously after exhaustion, or turn execution failure into measured validation failure. Any eventual adapter must preserve partial real evidence without promoting it to a successful checkpoint.

## Tested versus remaining acceptance

| Behavior | Status in this discovery |
| --- | --- |
| Actual app-server startup failure | Observed twice; raw errors retained |
| Installed host/plugin identity | Native Terminal metadata confirms installed/enabled Data 1.0.11; full executing-turn index output matches native remote Markdown hash |
| Supported Data invocation and analytical artifact retrieval | Demonstrated for one real synthetic stage; code, command execution and four fetched artifact byte hashes independently reviewed |
| Version propagation and mismatch rejection | Synthetic task/input/run binding passthrough verified; customer/source/proposal/approval/assumption propagation and rejection paths untested |
| Missing plugin or inaccessible plugin response | Not tested; startup failure must not be mislabeled as this outcome |
| Invalid analytical code | Native path untested; the successful stage executed valid code |
| Stage timeout and cancellation | Mock protocol path checked only; no native stage deadline expired or cancellation was exercised |
| Exhausted usage/recovery limits | Not tested; no native exhaustion event occurred |
| Needs data/material facts versus measured validation failure | Required distinction; no such outcome was manufactured or exercised |

No adapter is implemented. The engineering invocation and exact structural contract ACK clear those discovery questions, while full adapter acceptance still requires production-suitable capability binding, actual version/failure checks and parent integration. The successful probe preserves `automatic_DSC26_acceptance: false`. No Linear status, external application, remote branch, merge or deployment was changed by DSC-26.

## Remaining adapter and acceptance work

1. Use the verified native invocation mechanism in the adapter without depending on under-development plugin metadata methods. Confirm the intended executing host and provider route; the successful Terminal result does not establish managed-host or LiteLLM readiness.
2. Exercise real invalid-code, timeout/cancellation and exhausted-limit behavior, plus broader version propagation/mismatch handling. Retain the distinction between material gaps, measured validation failure and execution failure. Mock checks cannot satisfy those native outcomes.
3. Implement only the reserved adapter paths against the exact acknowledged DSC-24 snapshot and agreed DSC-10 parent interface. Independently verify input isolation, actual evidence retrieval and parent checkpoint handoff.
4. Customer execution additionally requires genuine DSC-25 approval of the current proposal and DSC-10 parent permission. Capability discovery does not grant either.

The assigned [DSC-26 issue](https://linear.app/gr3enarr0w/issue/DSC-26) and linked architecture/contract issues were accessible and read. The issue remains open for adapter implementation and remaining acceptance evidence.
