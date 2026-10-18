# Bounded native Data engineering probe

Historical observation for the run described below. Current isolated invocation, adapter wiring and remaining acceptance are documented in [ADAPTER.md](ADAPTER.md) and [NATIVE_BOUNDARY.md](NATIVE_BOUNDARY.md).

This probe exercises integration mechanics only. It is not the retail task, a customer analysis, a production adapter, a new runtime, or permission to bypass customer approval and parent checkpoints.

Run in the same normal macOS Terminal where the CLI catalog confirmed Data installed/enabled:

```sh
python3 /private/tmp/suiroai-dsc26/evidence/integration/probe_data_stage.py
```

The script creates a new temporary directory containing a three-row synthetic CSV and engineering version bindings. It does not receive the retail files. It asks one Codex turn to apply the installed OpenAI Data plugin, generate and execute calculation code, and save one result JSON. Unlike the earlier host checks, this step starts an actual model turn and may consume the signed-in account's Codex usage.

Before that turn, it reads native plugin metadata and remote skill Markdown for the actual installed Data identity. `plugin/read` is explicitly under development and is used here for engineering metadata discovery only; a production adapter must not depend on it. The stable documented remote `plugin/skill/read` and explicit skill/mention inputs are separate mechanisms. The script does not install Data, invent a Data endpoint, or copy its skills into a substitute standalone plugin. [App-server protocol](https://learn.chatgpt.com/docs/app-server)

Where the host supplies a usable skill path, the script uses that returned path. A remote plugin whose skill path is absent may instead be exercised through the documented plugin mention form using its verified native plugin identity. That is a candidate invocation to test, not proof that the host loaded Data. The accepted request and actual retrieved evidence must be reviewed together. [Native plugin-backed chat syntax](https://learn.chatgpt.com/docs/reference/commands)

The fetched skill Markdown is retained solely as native retrieval evidence. It is not pasted into the task prompt: the host must apply the actual skill or plugin attachment. This keeps the probe capable of detecting a native-loading problem.

The analytical turn has a 90-second deadline. On expiry, the script requests native interruption and waits briefly for a terminal outcome. It never grants a host permission request or silently retries, changes models, falls back to Code Interpreter, or continues after exhaustion. Discovery/retrieval requests have their own short timeouts. A native error, null skill contents, unsupported attachment, invalid result, missing executed-code evidence or incomplete retrieval remains inspectable failure or a blocker.

The script independently checks the actual result bytes, synthetic input hash, engineering bindings and calculation, and retains real host events and persisted item retrieval. Generated code or a result file alone is insufficient: evidence must show the code was actually executed. It prints the local evidence location for further review. Requests/responses with declared credential redactions, generated code, artifacts and native identifiers remain in that local probe directory.

Even a successful calculation does not automatically close DSC-26. Review must establish real Data loading and application, supported invocation and retrieval, version propagation, and the remaining invalid-code/cancellation/exhausted-limit behavior. Schema/mock checks and a model's self-report do not pass native integration acceptance.

Local review checked syntax, `--help`, native request/response schema shapes, and nine command-attribution examples including rejected echoes/conditional commands and accepted exact shell wrappers. Those checks do not exercise a real host or Data turn. No live model invocation was run from the managed environment when preparing this script.

## Remote identifier correction after the first real run

The user's first run stopped before creating a thread with `native_Data_plugin_not_installed_and_enabled`. Its native response supplied Data's correct remote identity/version but false installation/enabled flags. The [scoped observation](../../evidence/integration/remote-identifier-correction-2026-10-17/observation.json) retains the actual request and selected response fields, original evidence digest and no-turn outcome.

The probe incorrectly passed the display slug `data-analytics` as remote `plugin/read.pluginName`. Exact `rust-v0.163.0` source passes that field into a comparison against installed opaque plugin IDs. Metadata can resolve through the slug while that installed-ID comparison misses. Native tests pass the backend ID into this field. The corrected request uses `Plugin_fc9843a6fb34819195d6c7802398a8a7`; all returned identity, version and installation/enabled checks remain intact. A request-capture regression checks this exact payload without a live host/model invocation. This is a probe bug correction, not an authorization override or proof of a successful corrected turn. [Remote lookup implementation](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/core-plugins/src/remote.rs#L1438), [native tests](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/app-server/tests/suite/v2/plugin_read.rs#L195)

The user also identified the intended LiteLLM model gateway as `https://gateway.clarkeverson.com/v1` over HTTPS port 443, hosted internally at `192.168.192.115`, and stated they launch plain `codex`. This is supplied configuration context, not measured model-route evidence. This probe keeps the inherited Codex provider configuration. The failed run never reached model execution, so it did not test that gateway; no gateway, authentication or production-server setting was changed.

## Native remote access verified; thread request spelling corrected

The corrected opaque-ID request returned Data `1.0.11` as installed and enabled in the same app-server connection. Native `plugin/skill/read` then returned real index Markdown; its retrieved bytes match SHA-256 `a139924dda9dcab3e0207f69947b68de2b45f5d1bd997548c304735de397271e`. The [scoped observation](../../evidence/integration/thread-sandbox-correction-2026-10-17/observation.json) records identities, the actual error, original evidence digest, skill bytes/digest/reference and no-model-turn outcome. This establishes remote Data skill access, not application in an analytical turn.

The next request failed because the probe used the response policy discriminator `workspaceWrite` as the `thread/start.sandbox` request enum. The installed `0.163.0` request schema requires `workspace-write`; its response policy object still uses `type: workspaceWrite`. The request is corrected without changing the permitted sandbox scope. Direct native-schema validation rejects the old request and accepts the corrected one. No native thread or model turn was created by the rejected request.

Four [protocol regression tests](../../tests/integration/test_native_probe_protocol.py) now validate actual outgoing probe payloads against schemas freshly generated by the installed Codex CLI. They cover both attachment forms through the history-retrieval request, remote opaque identity, the distinct sandbox request/response enums, disabled-plugin blocking and timeout/interruption requests. Mocks deliberately stop before supplying any purported executed code/result artifacts. All four passed; these tests establish request conformance and local failure behavior only, not native Data execution acceptance.

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ceverson/Development/SuiroAI/suiroai/.venv/bin/python -m unittest discover -s tests/integration -p test_native_probe_protocol.py -v
```

## Real stage completed and independently reviewed

The user's corrected Terminal run completed native thread `01a14b70-b045-7751-b142-9a4af12556b6`, turn `01a14b70-b0f0-73f0-bc61-98047f5b24fe`, in 21,917 milliseconds. The host reported Codex `0.163.0`, model `gpt-6.1-sol`, provider `openai`, workspace-write sandbox and no network access. Data `1.0.11` was installed and enabled, including local version `1.0.11`; the accepted turn used `plugin://data-analytics@openai-curated-remote` without pasted skill Markdown.

The real executing turn read the installed Data index and shared instructions, generated `probe_calculation.py`, executed it with Python and read its result. Full streamed index bytes match native remote skill retrieval: 66,898 bytes, SHA-256 `a139924dda9dcab3e0207f69947b68de2b45f5d1bd997548c304735de397271e`. The persisted index output is explicitly truncated to 65,536 bytes; the full stream remains in the original native log. Other retained execution identities and the calculation/result evidence were checked against both streamed and persisted items. The generated-code change matches the retained code bytes.

Independent review verified all four fetched artifacts against their recorded hashes, byte counts and native source bytes. Recomputing the three-row CSV gives `A=5`, `B=5`, total `10`; the result preserves the exact engineering task/input/run binding and input digest. The native printed JSON matches the fetched result bytes. This demonstrates **one real bounded Codex/Data engineering invocation and artifact retrieval**, rather than a mocked calculation or model self-report.

The [retained review](../../evidence/integration/native-stage-2026-10-17/review.json) contains 27 checks, scoped command/host identities and the manual-review decision. It sits beside [input](../../evidence/integration/native-stage-2026-10-17/probe_input.csv), [binding](../../evidence/integration/native-stage-2026-10-17/binding.json), [generated code](../../evidence/integration/native-stage-2026-10-17/probe_calculation.py), [result](../../evidence/integration/native-stage-2026-10-17/probe_result.json) and their [integrity manifest](../../evidence/integration/native-stage-2026-10-17/SHA256SUMS.json). Full raw evidence stays at `/private/tmp/dsc26-data-stage-p71l6d8o/probe-evidence.json` and `native-rpc.jsonl`; the review records both byte digests. The committed projection omits proprietary skill text, agent reasoning and large raw logs.

**Full DSC-26 adapter acceptance remains incomplete; `automatic_DSC26_acceptance` remains false.** No production adapter or customer stage ran. Native invalid-code, timeout/cancellation and exhausted-limit handling, broader source/proposal/approval/assumption version checks, parent integration and actual file isolation remain outstanding. Metadata discovery used under-development `plugin/read`; production clients must use an agreed supported capability binding. The observed `openai` provider does not verify the user's intended LiteLLM gateway route, and the successful Terminal host does not resolve the earlier managed-host startup restriction.
