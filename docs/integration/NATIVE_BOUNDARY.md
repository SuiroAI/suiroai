# Native Codex/Data boundary

The supported synthetic invocation has been demonstrated with Codex CLI `0.163.0` and Data `1.0.11`. It does not establish customer input isolation. `NativeHost.execute` therefore rejects customer dispatch before starting a process. Explicit engineering mode is reserved for synthetic probes. The transport owns no analytical stages, parent decisions, retries or report logic.

The adapter uses native `codex plugin list --json` installed inventory, the exact Data plugin/config identity and remote ID, stable `plugin/skill/read`, and a documented native plugin mention in `turn/start`. It does not use the under-development `plugin/read` endpoint in production, invent a Data endpoint, install plugins or paste skill Markdown into the analytical prompt. It retains the fetched skill digest for inspection. Native mention acceptance alone does not establish skill application; reviewers must inspect actual Data resource reads and executed code/output.

The request's legacy sandbox enum is `workspace-write`; returned policy type is `workspaceWrite`. The native CLI-generated `0.163.0` schema confirms this distinction. The transport checks the returned cwd, approval policy and policy acknowledgement. These controls restrict writes and approvals, and do not establish released-input-only reads.

## Native isolation findings

The generated stable `TurnStartParams` schema at `/private/tmp/dsc26-native-protocol/v2/TurnStartParams.json` has no `ReadOnlyAccess`, `readableRoots` or restricted-read field in its legacy `SandboxPolicy`. Newer online app-server examples must not be assumed compatible with this installed binary.

The exact `rust-v0.163.0` source supports named permission profiles. The config format has filesystem read/write/deny entries and network settings. Native `thread/start.permissions` selects a named profile and cannot be combined with the legacy `sandbox` field; `runtimeWorkspaceRoots` and `activePermissionProfile` are also explicitly experimental protocol fields. [Native thread protocol](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/app-server-protocol/src/protocol/v2/thread.rs#L80), [permission config types](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/config/src/permissions_toml.rs#L112).

Official documentation describes a root deny with minimal platform reads, explicit input reads and output writes. It also warns that legacy sandbox settings override permission profiles. This is a candidate native mechanism, not an exercised isolation claim for this host. No experimental profile selection or configuration change has been made here. [Permissions](https://learn.chatgpt.com/docs/permissions)

A narrow future engineering probe can create a released synthetic file, an unreleased synthetic sentinel outside the release root, and a writable output directory. A native permission profile would deny root reads, allow minimal runtime and installed Data resources, grant released files read access and outputs write access, and disable command networking. The probe must retrieve genuine events showing permitted input reads and output writes succeeding, direct sentinel reads failing, and effective native profile identity. It must also address connector/file-tool access rather than assuming a filesystem rule disables those tools. `disabledPluginIds` alone does not prove capabilities are filtered. Do not use customer files for this test.

Until this is exercised, customer dispatch returns `unsupported_integration`. A new cwd or a date-filter prompt is insufficient. No separate sandbox service or custom runtime is authorized.

The next engineering check is now prepared:

```sh
python3 /private/tmp/suiroai-dsc26/evidence/integration/probe_native_isolation.py
```

Run it in the normal Terminal that completed the earlier native probes. It uses
fresh synthetic files and process-scoped configuration overrides. Global Codex
configuration is not edited. Metadata and deterministic command controls have a
120-second bound; at most one 90-second Data turn follows, with bounded cleanup.
Named profile fields are explicitly experimental for CLI 0.163.0.

The declared worker is tabular: native image/browser/web tools, memories, other
plugins, apps and configured MCP servers are disabled for this process. The probe
checks effective configuration and actual thread MCP inventory before the Data
turn. Empty config tables are not treated as removing inherited connectors;
each discovered connector is disabled explicitly. It does not test or claim
native image-tool denial. See the [source audit](ISOLATION_PROBE.md) for the
stable-history limitation that led to this explicit scope.

Native command controls must show a real released-file calculation and output
write, plus genuine permission errors for an existing unreleased sentinel,
its symlink, protected-input/outside-output writes and a controlled network
connection. Trusted-side hashes preserve the distinction between denial and a
missing or changed fixture. If these checks pass, one native Data turn must
read its actual installed resources, execute code, and return matching artifact
bytes under the same profile. Missing receipts, unexpected tools, rejected
configuration or partial inventory produce an honest blocker. No probe status
automatically enables customer dispatch or closes DSC-26.

The first isolation attempt stopped before native controls or a model turn with
`Effective native filesystem/network profile differs`. Its original selected
filesystem/network object was not retained, so the mismatched field is unknown.
The exact CLI source serializes an absent optional `glob_scan_max_depth` as JSON
`null`; the probe's raw dictionary comparison rejected that representation.
Commit `5daa5b1` normalizes only this known absent/null metadata and preserves
exact grant and disabled-network checks. Subsequent failures retain and print
a safe comparison for the selected profile. This is a source-supported likely
explanation, not a retrospective observation or passed isolation check.
[Original blocked observation](../../evidence/integration/isolation-profile-comparison-2026-10-17/observation.json)

The following real run accepted the requested profile but failed native controls:
sentinel and symlink reads succeeded, and an actual empty file was created
outside the output namespace. Input writes and networking were denied. No model
turn ran. The [retained failure](../../evidence/integration/native-command-isolation-failure-2026-10-17/review.json)
contains exact request/response receipts and verified artifacts.

The exact native macOS source adds Process scratch reads/writes under
`/private/tmp` and `/private/var/tmp` when `:minimal` is active. A filesystem-root
deny alone does not exclude those implicit grants. This is shared native
behavior, not evidence of a lossy `command/exec` conversion. Commit `11ec77e`
adds explicit physical scratch-root and canonical current `TMPDIR` denies,
preserving the narrower released-input and output grants. The same denied test
fixtures remain under `/private/tmp`; they were not moved to conceal this
failure. Actual enforcement of the strengthened profile still needs a real
probe. The console now retains individual native control outcomes even when
the checker exits nonzero. See the [source audit](ISOLATION_PROBE.md).

## Failure evidence

`evidence/integration/probe_native_failures.py` provides one normal-Terminal command for three synthetic probes: intentional invalid Python without repair, cancellation only after an actual native `turn/started` event, and a finite timeout. Each turn has a 60-second total native-operation bound, with at most ten extra seconds for interrupt acknowledgement and bounded process cleanup. The script reports actual observed results or incomplete evidence; it never grants automatic acceptance.

A fourth case supplies a declared zero-time budget and requires `budget_exhausted` before any thread or turn exists. This is a measured predispatch bound check, not upstream quota exhaustion; no quota depletion is attempted.

The [independent four-case review](../../evidence/integration/native-failures-2026-10-17/review.json) retains compact observations, the invalid/wait scripts and original raw-evidence paths/hashes. It omits full skill text, reasoning and large native logs. `automatic_DSC26_acceptance` remains false.

- **Invalid code:** the real command `exec-c838dba9-c532-41b3-9018-c647228fd28f` failed with exit `1` and an actual `SyntaxError`; streamed and persisted command items match. The retained 13-byte script independently fails compilation. The original adapter incorrectly returned `completed` with no error code because it did not recognize the observed compound `printf`/newline/Python command. That original result is preserved. Corrected classifier commit `ef8fcdbff36646ce83f345c6db4b0f1d7f9920a1`, source SHA-256 `cc3b1ccc28ae1eaa97de1e05e4d5dd3f2267f31d003405df98f5b6a889661056`, recognizes the exact command in an **offline replay of the real saved evidence**. No corrected live model turn or original `invalid_code` adapter return is claimed. [Observation and replay](../../evidence/integration/native-failures-2026-10-17/invalid_code.json)
- **Cancellation:** a real `turn/interrupt` request received an acknowledgment and matching `interrupted` terminal. It occurred 183 ms after turn start, before any analytical command event; it does not establish termination of running Python. [Observation](../../evidence/integration/native-failures-2026-10-17/cancelled.json)
- **Timeout:** the native operation returned `timeout` and a matching `interrupted` terminal. A Python wait command had started and printed its actual wait marker before the deadline. The log retains interruption and terminal timestamps, but no matching command-completed or OS-process-exit receipt; process termination remains unverified. [Observation](../../evidence/integration/native-failures-2026-10-17/timeout.json)
- **Declared zero time:** the transport returned `budget_exhausted` without creating a thread or turn. This verifies the local supplied-bound guard, while native account/usage quota exhaustion remains unexercised. [Observation](../../evidence/integration/native-failures-2026-10-17/declared_zero_time.json)

Native invalid-code classification requires a nonzero Python execution with matching streamed and retrieved command identity/output containing an actual Python syntax exception. Prose saying code failed is insufficient. Timeout and cancellation preserve their original outcome after an interrupt, and partial results remain diagnostic. Exhausted host limits map to `budget_exhausted`; real limit exhaustion remains unexercised.

Any failure while a native turn is known active requests interruption before cleanup and retains the original error classification. Evidence retention has a finite bulk cap with a small reserved control receipt allowance; exhausting logging cannot prevent the interrupt request or terminal wait. An unconfirmed interruption is recorded explicitly and never becomes success.

Routine logs remain internal and preserve native IDs and artifact provenance. Auth/attestation server request parameters are omitted, all such requests are rejected, and common credential fields are redacted. The adapter never grants additional permissions. Model routing is unchanged: LiteLLM routing for the analytical host remains unverified and must not be inferred from a successful answer or the provider label alone.
