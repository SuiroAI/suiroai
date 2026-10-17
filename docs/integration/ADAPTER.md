# DSC-26 adapter boundary

The native Codex 0.163.0 app-server has demonstrated one real, bounded synthetic
stage with OpenAI Data 1.0.11. See the independently reviewed
[invocation evidence](../../evidence/integration/native-stage-2026-10-17/review.json).
This establishes native invocation and retrieval, not customer execution or
completion of DSC-26.

The current [DSC-26 issue](https://linear.app/gr3enarr0w/issue/DSC-26) was read
through the connected Linear get-issue tool on October 17, 2026. Its reported
update time was `2026-10-17T04:39:53.799Z`. No issue state or other external
application was changed. Its requirement for separate invocation, version,
failure and exhausted-budget evidence remains in force.

## Owned components

- `integration.artifacts.ArtifactStore` measures and stores immutable exact
  references. It stages only `released_input_refs`; it performs no preparation,
  filtering, joining or temporal release decisions. The trusted parent supplies
  the release and upstream content-validation evidence.
- `integration.native.NativeHost` uses the installed CLI and supported native
  app-server methods. Customer mode currently fails before launching a model:
  released-input-only native read isolation has not yet been exercised. Explicit
  engineering mode is reserved for synthetic probes. It does not grant customer
  permission or satisfy customer acceptance.
- `integration.adapter.StageAdapter` consumes the existing submission, proposal,
  approval, execution contract and exact stage request. It verifies measured
  references and the DSC-24 snapshot, then calls a trusted DSC-10 callback for
  permission on that exact request. Worker JSON cannot authenticate the parent.
  The adapter never changes the goal/output or creates a new task-definition
  stage. It returns `parent_decision: null`; DSC-10 decides transitions and
  bounded recovery.

The dependency snapshot is DSC-24 `0.1.0-draft.3`, released in owner commit
`487a8dc9aedd3b4de34efe9d76f2eec94d58d2f8`. Owner commits were pulled into this
worktree without changes to shared files. The adapter pins the agreed schema
and validator hashes. Schema changes must go through DSC-24 and DSC-3.

## Call boundary

Construct `StageAdapter(store, work_root=..., parent_permits=...)`, then call
`execute(stage_request_ref, handoff_refs=[...], external_refs=[...], cancellation=event)`.
The handoff contains one current submission/approval chain and required upstream
typed evidence. External references must be registered, measured bytes, not
unverified hashes. Invalid or unauthorized handoffs raise `AdapterRejected`
before a worker starts. Valid exhausted, expired, cancelled or unsupported
requests produce a typed `execution_failed` result with retained adapter evidence.

`allow_mock_handoffs=True` exists only for explicit consumer development. Its
results retain mock provenance. It never disables the native customer-isolation
gate and never establishes real acceptance.

The worker transport uses two adapter-private files within a fresh stage
directory: `stage-result.json` matching the shared `stage_result` schema, and
`artifact-manifest.json`, a list of `{ref, path, encoding}` entries. `path` is
relative; `encoding` is `bytes` or `record`. The adapter verifies the entire
returned handoff and actual bytes before accepting outputs. These filenames
are an internal transport convention, not new shared business contracts.

One dispatch consumes the parent's remaining time and stage limits; it does not
refill budgets or retry. Timeouts/cancellation request native interruption and
retain whether native interruption was confirmed. Partial execution evidence
cannot become successful analytical output. Nonpositive relevant limits reject
before launch; unrelated zero limits do not block other stages.

Actionable `needs_inputs`/`needs_material_facts` gaps retain evidence. A measured
`validation_failed` result requires the actual failed final-validation artifact.
Invalid code, plugin/transport errors, timeouts, cancellation, exhausted limits
and integrity failures remain execution failures. No second-best fallback or
checkpoint decision is made here.

Artifact storage is not a transaction or a parent acceptance decision. All
returned outputs are checked before publication; immutable identity checks run
before a batch writes. A storage failure may leave measured receipts in the
store, but the failure result returns no successful output references. Its audit
records actually published references without claiming those receipts are
quarantined. Consumers must use the returned stage result and parent decision,
not infer acceptance from the presence of a stored object.

## Checks completed locally

On October 17, 2026, 56 integration tests passed, including schema checks against
the installed native CLI, approval/version mutations, source-byte integrity,
typed failure/gap distinctions, interruption requests and immutable output
collisions. All simulated execution fixtures are explicitly mocked. The 77
unchanged DSC-24 contract tests also passed, and all seven release-snapshot file
hashes matched.

The actual native adapter's zero remaining-time guard was separately exercised
without a mock: it returned `budget_exhausted` with no thread, turn or native
log. See [the declared-limit check](../../evidence/integration/declared-limit-2026-10-17/check.json).
This is a predispatch guard check, not analytical execution or provider-quota
exhaustion. Actual successful invocation evidence remains the separately
reviewed synthetic native stage.

## Current blockers

Customer dispatch requires a demonstrated supported native read policy that
excludes unreleased data. A fresh cwd, read-only copies and the legacy
`workspace-write` write sandbox do not establish that boundary. The raw sales
file contains December outcomes and must not enter development context. No
custom runtime or prompt-only substitute is implemented.

Native invalid-code and interruption checks require real Terminal execution;
mocked transport tests alone cannot close them. The intended LiteLLM gateway
route is not demonstrated by a native `modelProvider: openai` field. Real
customer execution also requires DSC-25 approval and DSC-10 permission for the
exact approved versions. No customer analysis has run.

The next bounded, synthetic-only check is:

```sh
python3 /private/tmp/suiroai-dsc26/evidence/integration/probe_native_failures.py
```

Run it in the user's normal Terminal, where the previous native invocation
succeeded. The managed execution environment previously failed app-server
startup with `Operation not permitted`. The command runs at most three model
turns, each limited to 60 seconds plus bounded interruption/cleanup, and one
zero-time noninvocation check. It records genuine results or incomplete evidence
for manual review; it does not close the issue.
