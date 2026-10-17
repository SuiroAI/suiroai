# Bounded native Data engineering probe

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
