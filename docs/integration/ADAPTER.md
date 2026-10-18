# DSC-26 adapter boundary

Codex CLI `0.163.0` with OpenAI Data `1.0.11` demonstrated a real bounded
synthetic calculation under the reviewed native release/output profile.
The [independent review](../../evidence/integration/native-isolated-stage-2026-10-17/review.json)
records 26 checks, actual commands, retrieved code/results and model-delegated
permission denials. The adapter now uses that mechanism. Its complete approved
customer-packet path has not been exercised live; engineering evidence does not
authorize a customer run or close DSC-26.

The current [DSC-26 issue](https://linear.app/gr3enarr0w/issue/DSC-26) was read
through the connected Linear tool on October 17, 2026, with reported update time
`2026-10-17T04:39:53.799Z`. At the user's request, next-round integration
requirements were appended to DSC-25 and DSC-10 and read back successfully.
Issue statuses were unchanged.

## Owned components

- `ArtifactStore` measures immutable exact references and stages only the
  parent's `released_input_refs`. It performs no preparation, temporal release
  decisions or joins. The trusted parent supplies release/content evidence.
- `NativeHost` invokes the installed CLI's native app-server with the Data
  mention and pinned native skill. Customer mode requires the reviewed physical
  sibling release/output/evidence roots and verifies effective native controls.
  Explicit engineering mode without a release root retains the legacy synthetic
  probes; that mode cannot satisfy a customer result.
- `StageAdapter` consumes the existing submission, proposal, approval, execution
  contract and exact stage request. It verifies measured references and the
  agreed DSC-24 snapshot, then requires the trusted DSC-10 callback to permit
  that exact request. It preserves the approved goal/output and version bindings.
  Returned `parent_decision` stays null; DSC-10 owns transitions and recovery.

The unchanged DSC-24 snapshot is `0.1.0-draft.3`, owner release
`487a8dc9aedd3b4de34efe9d76f2eec94d58d2f8`. Schema and validator hashes are pinned.
Shared contract changes remain with DSC-24/DSC-3; no public DSCraft interface or
intake, modeling or report logic is added.

## Call boundary

Construct `StageAdapter(store, work_root=..., parent_permits=...)`, then call
`execute(stage_request_ref, handoff_refs=[...], external_refs=[...], cancellation=event)`.
The handoff must include the current approval chain and required upstream typed
evidence. External references must resolve to measured stored bytes. Invalid or
unauthorized handoffs raise `AdapterRejected` before native dispatch. A valid
exhausted, expired, cancelled or unsupported request returns a typed execution
failure with adapter evidence. Store bounds must support a minimal failure packet.

`allow_mock_handoffs=True` supports explicitly mocked consumer development with
an injected mock host. Mock provenance remains attached. A mock handoff can
never dispatch a real `NativeHost`, even when that option is enabled.

Each attempt has fresh physical sibling `released`, `output` and `native`
directories. Only released copies and their measured manifest enter the worker
read grants; output is the native cwd and writable root. The controller retains
native logs separately. The [native boundary](NATIVE_BOUNDARY.md) documents the
host pins, effective controls, experimental protocol fields and tool limits.
An offline comparison confirmed the production profile configuration is
semantically equal to the actual successful probe's configuration.

The worker writes `stage-result.json` matching the shared `stage_result` schema
and `artifact-manifest.json`, a list of `{ref, path, encoding}` entries. Paths are
relative to output; encoding is `bytes` or `record`. These are private transport
filenames, not new shared business contracts. Full handoff, actual artifact
bytes, immutable identities, lineage bindings and parent-owned fields are
validated before publication. Released files and manifest are remeasured after
the native run, including failed runs.

Native logs/report become immutable measured references with hashes and sizes
on both successful retrieval and execution failure. Bulk skill/reasoning bodies
and credential-bearing configuration are omitted. The bounded binding audit
points to full sanitized native receipts. Per-file and aggregate limits include
native evidence, published worker objects, controller audit and returned result;
large optional failure details are compacted to explicit measurements.

Discovery, setup, execution and retrieval consume one original approved stage
deadline. No automatic retry or budget refill occurs. Cancellation and expiry
request native interruption and retain whether it was confirmed. Immediately
before final result publication the adapter checks cancellation/deadline again;
that publication commits the checked result, so a subsequent cancellation cannot
create a second contradictory result.

`needs_inputs` and `needs_material_facts` preserve actionable gaps separately.
`validation_failed` requires the actual failed final-validation artifact.
Invalid code, plugin/transport failure, cancellation, timeout, exhausted limits
and integrity failure remain execution failures. Native completion or model
prose alone cannot establish analytical success. The adapter makes no fallback,
checkpoint or customer-response decision.

Storage is not a batch transaction or parent acceptance. A storage failure may
leave measured diagnostic receipts. The returned failure has no successful
output refs and records what was published; consumers must use the returned
result and parent decision, not infer acceptance from stored object presence.

## Verification and cross-PR integration

On October 17, 2026, all 127 integration tests passed. The suite covers
approval/version mutations, source and result
integrity, isolated roots/profile acknowledgements, disabled inventories,
immutable native receipts, bounded discovery, failure/gap distinctions,
interruption and late-cancellation accounting. Execution fixtures in these tests
are explicitly mocked and never establish real invocation acceptance. The 77
unchanged DSC-24 contract tests and seven release snapshot hashes were verified.
An earlier full run had an inventory process-group cleanup failure; the exact
test, focused investigation and final full suite passed without weakening
cleanup. Its original transient cause is unknown.

Real engineering evidence establishes the native mechanism and actual artifact
retrieval. [Separate failure evidence](../../evidence/integration/native-failures-2026-10-17/review.json)
records cancellation and timeout interruptions, an actual invalid Python command
and offline correction replay, and a real zero-time non-dispatch guard. It does
not prove OS termination of a running Python process or provider quota depletion.

DSC-25 approval and DSC-10 parent orchestration are owned by separate PRs.
Their later integration must exercise the complete adapter with genuine approved
versions and review its actual artifacts. Those dependencies do not expand this
adapter PR or prevent its independent review. No customer analysis has run. Native profile fields are experimental and pinned
to this macOS workstation. A negative patch permission check remains
unexercised; image tools are disabled. The loopback denial proves the tested
connection, not all possible networking. Intended LiteLLM/gateway routing also
remains unverified. See [native scope and evidence](NATIVE_BOUNDARY.md).
