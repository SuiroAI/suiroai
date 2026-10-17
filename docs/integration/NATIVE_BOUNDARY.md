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

## Failure evidence

`evidence/integration/probe_native_failures.py` provides one normal-Terminal command for three synthetic probes: intentional invalid Python without repair, cancellation only after an actual native `turn/started` event, and a finite timeout. Each turn has a 60-second total native-operation bound, with at most ten extra seconds for interrupt acknowledgement and bounded process cleanup. The script reports actual observed results or incomplete evidence; it never grants automatic acceptance.

A fourth case supplies a declared zero-time budget and requires `budget_exhausted` before any thread or turn exists. This is a measured predispatch bound check, not upstream quota exhaustion; no quota depletion is attempted.

Native invalid-code classification requires a nonzero Python execution with matching streamed and retrieved command identity/output containing an actual Python syntax exception. Prose saying code failed is insufficient. Timeout and cancellation preserve their original outcome after an interrupt, and partial results remain diagnostic. Exhausted host limits map to `budget_exhausted`; real limit exhaustion remains unexercised.

Any failure while a native turn is known active requests interruption before cleanup and retains the original error classification. Evidence retention has a finite bulk cap with a small reserved control receipt allowance; exhausting logging cannot prevent the interrupt request or terminal wait. An unconfirmed interruption is recorded explicitly and never becomes success.

Routine logs remain internal and preserve native IDs and artifact provenance. Auth/attestation server request parameters are omitted, all such requests are rejected, and common credential fields are redacted. The adapter never grants additional permissions. Model routing is unchanged: LiteLLM routing for the analytical host remains unverified and must not be inferred from a successful answer or the provider label alone.
