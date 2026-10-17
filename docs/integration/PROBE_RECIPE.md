# Actual DSC-26 engineering probe recipe

2026-10-17. This is a record of a one-off capability probe, not an application transport or an analytical runtime.

The local executable was inspected with `command -v codex`, `codex --version`, `codex exec --help`, and `codex app-server --help`. The executable was `/opt/homebrew/bin/codex`, reporting `codex-cli 0.163.0`.

Two Python standard-library harness invocations used `subprocess.Popen` with separate stdin/stdout/stderr pipes, text mode, `bufsize=1`, and `selectors.DefaultSelector`. Working directory: `/Users/ceverson/Development/SuiroAI`. The child argument lists were:

```json
["codex", "app-server", "--listen", "stdio://"]
```

```json
["codex", "app-server", "--listen", "stdio://", "-c", "sqlite_home=\"/private/tmp/dsc26-host-state\""]
```

The second harness created only the permitted temporary state directory with `Path.mkdir(exist_ok=True)`. It did not change `CODEX_HOME`, copy authentication, edit host configuration, enable experimental API capabilities, or override host permissions.

The harness wrote this JSON request followed by a newline and flushed stdin:

```json
{"id":1,"method":"initialize","params":{"clientInfo":{"name":"dsc26_engineering_probe","title":"DSC-26 engineering capability probe","version":"0.1.0"}}}
```

Only after a successful response with `id: 1` would it have sent these messages:

```json
{"method":"initialized","params":{}}
{"id":2,"method":"skills/list","params":{"cwds":["/Users/ceverson/Development/SuiroAI"],"forceReload":true}}
```

Neither was sent: the child exited before the initial response. No `thread/start`, `turn/start`, code execution, file-transfer or analytical request was included in either harness.

The harness selected stdout/stderr in 0.5-second intervals with an overall 25-second monotonic deadline. It stopped on a discovery response, initialization error or process exit; cleanup requested process termination with a three-second wait and kill fallback. It saved received lines, actual sent requests, UTC time, child return code and `analytical_invocation: false`. Neither probe reached the deadline. This cleanup behavior is not an exercised Codex turn cancellation.

The two original JSON records were saved in `/private/tmp/dsc26-appserver-discovery.json` and `/private/tmp/dsc26-appserver-discovery-writable-state.json`, then copied without modification into [the evidence directory](../../evidence/integration/discovery-2026-10-17/). Their byte hashes appear in `SHA256SUMS.json`. No model response, synthetic tool output, fixture result or mock was added to those records.

## Follow-up host diagnostic

The standalone [probe_host.py](../../evidence/integration/probe_host.py) now reproduces the initialization and skill-discovery check with a 20-second deadline. It never creates a thread or starts a model turn. Its default launch reproduced the SQLite startup failure in this managed session. The user's normal Terminal subsequently completed initialization and discovery; the actual returned skill list lacked Data. See [TERMINAL_DISCOVERY.md](TERMINAL_DISCOVERY.md).

Run from the user's ordinary signed-in macOS Terminal to compare environments:

```sh
python3 /private/tmp/suiroai-dsc26/evidence/integration/probe_host.py
```

It prints handshake/discovery status and the path to a temporary JSON observation. If initialization succeeds, it lists Data skills observed by that executing host. That is readiness evidence only; a real bounded Data turn, artifact retrieval and failure checks are still needed.

A failed run in the ordinary Terminal calls for diagnosis of that host's specific error. A successful run there with failure here establishes a difference between launch environments, without by itself identifying which permission or configuration causes it. No policy bypass or broad permission change is part of this diagnostic.

To inspect the executing CLI's plugin catalog as well, use:

```sh
python3 /private/tmp/suiroai-dsc26/evidence/integration/probe_host.py --plugins
```

This first runs the supported read-only `codex plugin list --available --json` command, bounded to 25 seconds, then performs the same host check. It does not install, enable, remove or copy any plugin. The summary includes only matching Data catalog entries and catalog errors; the full native response stays in the local observation file. A remote-catalog error means a partial list cannot prove Data unavailable. This option was exercised inside the managed environment and retained its native remote-request warning and startup error; it has not yet been verified in the user's Terminal. [Official CLI reference](https://learn.chatgpt.com/docs/cli/reference)
