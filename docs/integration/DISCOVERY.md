# DSC-26 supported-interface discovery

Revision 0.1.0 · 2026-10-17 · **Integration blocked; no real analytical invocation demonstrated.**

Later evidence: the user's normal Terminal successfully initialized this app-server and completed skill discovery, but its returned skills lacked Data. See [TERMINAL_DISCOVERY.md](TERMINAL_DISCOVERY.md). The managed-environment failures below remain historical observations. The [draft.3 contract review](CONTRACT_REVIEW.md) now records DSC-26's exact structural ACK; native Data execution is the remaining capability blocker.

The user's subsequent native CLI catalog query also confirmed Data `1.0.11` installed and enabled as `data-analytics@openai-curated-remote`. Installation is therefore verified for that Terminal context. Its absent `skills/list` entry is not sufficient to declare remote Data unavailable: the official protocol separately documents on-demand remote skill retrieval. Native retrieval and actual invocation remain to be exercised; reinstalling or copying the cached skills is not justified by these results.

## Observed result

The installed Codex CLI reports `codex-cli 0.163.0`. Two engineering probes attempted the documented app-server stdio interface. Both child processes exited with code 1 before replying to `initialize`. Neither reached `skills/list`, `thread/start`, or `turn/start`. No synthetic calculation or customer analysis ran, and no analytical artifact was produced or retrieved.

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

The JSON observations are discovery records, **not instances of an invented shared execution/result/evidence schema**. DSC-24 remains the sole owner of that schema. There is no customer task/proposal/approval/source version because no customer stage was submitted. Installed-file hashes establish observed identity only; propagation through an executing turn remains untested.

## Adapter boundary after prerequisites clear

Consume DSC-24's agreed execution/result contract and the same task proposed in DSC-25 step 2 and approved in step 3. Require DSC-10 parent permission before any customer invocation. Transfer only the contract-authorized file references, actions, as-of context and limits; return outcomes and immutable evidence for parent checkpoint decisions. The adapter owns no intake, cleaning, feature definitions, modeling, restocking arithmetic, report content, parent transitions, retry decisions or final delivery authorization.

Before invoking a customer stage, independently check task/run/input/proposal/approval/assumption versions and file accessibility. The executing worker must receive only permitted development artifacts for feature generation and selection. Giving unrestricted December rows to a development turn is prohibited; a prompt telling it to ignore those rows is insufficient isolation. Final evaluation requires parent-authorized frozen references and holdout release. The November 30 forecast remains immutable.

On a verified host, retain actual thread/turn identifiers, outbound skill attachment, executable and plugin/skill identity, executed code/config and outputs, final status, and artifact bytes/digests. Validate version bindings and returned artifact identity independently. If history normalizes skill input, retain the accepted outbound request with retrieved execution items. Host turn completion alone does not pass an analytical checkpoint. Result text that claims a calculation ran does not substitute for code/output/artifact evidence.

Enforce a finite deadline and declared limits around the supported mechanism. Interruption must have an observed terminal outcome; an interrupt request alone does not prove cancellation. Never accept late artifacts as a current success, retry autonomously after exhaustion, or turn execution failure into measured validation failure. Any eventual adapter must preserve partial real evidence without promoting it to a successful checkpoint.

## Tested versus remaining acceptance

| Behavior | Status in this discovery |
| --- | --- |
| Actual app-server startup failure | Observed twice; raw errors retained |
| Installed host/plugin identity | CLI version, manifest and skill hashes recorded; executing-host skill discovery not reached |
| Supported Data invocation and analytical artifact retrieval | Not demonstrated; blocked before handshake |
| Version propagation and mismatch rejection | Not tested; no stage ran |
| Missing plugin or inaccessible plugin response | Not tested; startup failure must not be mislabeled as this outcome |
| Invalid analytical code | Not tested; no analytical worker ran |
| Stage timeout and cancellation | Not tested; the discovery watchdog did not time out and process cleanup is not stage cancellation |
| Exhausted usage/recovery limits | Not tested; no native exhaustion event occurred |
| Needs data/material facts versus measured validation failure | Required distinction; no such outcome was manufactured or exercised |

No adapter is implemented: the real mechanism has not been verified, and the DSC-24 snapshot was still under owner review during discovery. Mock tests cannot remove either prerequisite. No Linear status, external application, remote branch, merge or deployment was changed by DSC-26.

## Exact unblock conditions

1. An authorized host must start successfully and discover the Data skill for its execution directory. Preserve the real handshake/discovery responses; do not infer readiness from local files.
2. Exercise a bounded, clearly labeled synthetic engineering turn with explicit Data attachment. Retrieve actual execution items and generated artifact bytes, verify expected contents and hashes, then exercise version/failure behavior. These are engineering probes, not customer analysis.
3. DSC-24 and DSC-3 must agree the concrete interface snapshot. Implement only the reserved adapter paths against that version.
4. Customer execution additionally requires genuine DSC-25 approval of the current proposal and DSC-10 parent permission. Capability discovery does not grant either.

The assigned [DSC-26 issue](https://linear.app/gr3enarr0w/issue/DSC-26) and linked architecture/contract issues were accessible and read. The issue remains open for real invocation evidence.
