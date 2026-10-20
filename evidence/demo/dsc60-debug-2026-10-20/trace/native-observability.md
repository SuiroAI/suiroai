# DSC-60 native LLM trace observability

Scope: inspect the exact failed final run `artifacts/demo/f8567dcea15e473380dbcfc067ccf092/runs/investigation-fd2a074d16e7401ca1682ad64e944847/`, its retained native logs and current transport source. This is workflow tracing, not another analysis or model selection. No new model call, raw-input parsing, December outcome access, or shared-module edit occurred.

## What the failed run records

| Surface | Observable evidence | Limit |
|---|---|---|
| Outbound task | `native-rpc.jsonl`, sent RPC id 7 `turn/start`: text prompt, Data mention `plugin://data-analytics@openai-curated-remote`, `effort=medium`, thread ID | Stored JSON passes through `project_message`/`sanitize`; this is an inspectable application request, not a byte-for-byte network capture or complete model context. |
| Prompt identity | Stored prompt: 10,154 UTF-8 bytes; SHA-256 `08ef73b34587998eb9b8f64cd15a7b29ed955a1ed1246b7bb80f351412e87b99`. Canonical stored turn params, sorted keys, UTF-8 JSON, compact separators: `08c5684cc9900fe338a4de3be701fdc44b8270a370793e691f32c5592b159229` | Hash is of retained, sanitized values; do not label it a pre-sanitization or provider-input hash. |
| Model/runtime request | Sent id 5 `thread/start`: `gpt-6.1-sol`, approval `never`, named permission profile, output cwd and runtime workspace root. Returned acknowledgement: OpenAI provider, model, medium reasoning effort, CLI `0.163.0`, default service tier | Requested/acknowledged public configuration, not provider internals, effective hidden prompt, random seed or deterministic execution guarantee. |
| Data identity | Installed remote plugin `data-analytics@openai-curated-remote`, version `1.0.11`, remote ID `Plugin_fc9843a6fb34819195d6c7802398a8a7`; inventory command, exit, byte counts and stdout/stderr hashes | Inventory proves identified installation, not all instruction text in the model's context. |
| Data index resource | `plugin/skill/read` reply id 4: body omitted, 66,898 bytes, SHA-256 `a139924dda9dcab3e0207f69947b68de2b45f5d1bd997548c304735de397271e`; compared to pinned hash by transport | Transport reads/verifies this resource but sends the Data mention, not the fetched markdown as explicit text. Runtime plugin instruction injection is not exposed as a full provider prompt. |
| Restrictions | `effective_profile_verified=true`, profile filesystem grants and network false, projected effective feature flags, web search disabled, disabled MCP inventory before/after; only Data enabled by verified config | Logs intentionally project config, excluding arbitrary config values, endpoints and credentials. Full config layers and source of all instruction settings are unavailable. |
| Tool actions | 41 final items: 12 command executions, 6 file changes, 4 agent messages, 18 omitted reasoning items, 1 user message. Commands include shell reads of skills, data profiling, `python analyze.py`, output checks, notebook creation. Cwd, command, exit, duration, action metadata and paired completed events retained | No inference that a listed path was fully understood or followed. Matching event/retrieval items attest observed activity, not correctness of conclusions. |
| Instruction reads | Three command items read index, product-business-analysis/shared instructions/analysis-quality, and gather-business-context/analyze-data-quality/jupyter-notebooks. Command strings retain resource paths; output bodies are omitted with output byte/hash receipts | Combined commands have combined output hashes, not per-file instruction identity. Index shell output is 65,536 bytes, different from 66,898-byte API body; possible tool output truncation. Do not claim the full index body reached the model through this shell read. |
| Tool outputs | Ordinary completed-command `aggregatedOutput` remains in retained logs; nine streamed output deltas omit payloads and retain canonical JSON byte/hash receipts. stderr retains byte/hash receipts only | Stream payload hash is for canonical JSON payload, not raw stdout. Omitted bytes cannot be recovered from a hash; aggregated output can itself be tool-truncated. Existing ordinary outputs include data previews, so avoid copying them into broader trace receipts. |
| Produced artifacts | File-change events, matching retrieval, bounded file hashes, retained `analyze.py`, audit/evaluation files, final response and CSV | Current output bytes describe final artifact state; they do not automatically prove every intermediate file version. |
| Lifecycle | Thread `01a1575b-73d5-7d92-9fcd-c2731c132181`, turn `01a1575b-7471-7af1-8765-ea1e4c43e05d`, completed terminal status, monotonic event order | Completion does not mean analytical acceptance. Wall-clock provenance and external chronology need explicit receipts. |

## Visible failure chain and attribution limits

The outbound task explicitly delegates method and target decisions to Data, asks for honest same-data comparisons, and directs mixed/no-improvement results to be stated plainly. The trace then shows the Data worker writing/executing its chosen `analyze.py`, reading comparison outputs and writing its answer. Retained generated code exposes its early-window selection rule and the later evaluation window; its final selected approach and answer can therefore be traced to concrete visible tool actions. This is enough to debug where the observable workflow failed to enforce its own comparison requirement and to test a changed task contract with the same public runtime settings.

It does not establish a unique psychological or hidden-prompt cause. Base/system/developer context assembled by the Codex host, runtime plugin injection, exact provider request/context packing, instruction precedence as resolved internally, compaction, reasoning and private model state are not supplied through this interface. Reasoning events are deliberately omitted; they should stay omitted. Do not claim those unsupported surfaces were captured, absent, unchanged or causal. `config/read` uses `includeLayers=false`, and its retained projection omits instruction bodies; it cannot settle whether other host instruction settings existed.

## Safe tracing recommendation

Keep raw task text inside the already restricted native evidence location; link/hash it in the new receipt. Record requested and acknowledged public model/effort/runtime identities, profile verification, attached plugin identity, pinned index resource hash, and ordered tool-command/event references with existing output hashes/omission flags. Add per-resource hashes for only observed instruction paths if locally available and explicitly label measurements as post-run resource identity, not proof of historical contents; preserve combined historical output hashes separately. Bind final generated script, response and result checksums into the same receipt.

This supports a before/after Data task experiment without widening raw customer-output logging, duplicating skill bodies, logging secrets/config dumps, or exposing hidden reasoning. Hashes establish identity and change detection; they do not authenticate hidden context or prove instructions were followed. Keep ordinary output previews under existing retention controls. The useful causal test is a bounded new Data run with a changed task contract and otherwise documented visible settings, followed by inspection of generated decisions and their measured comparison—not a claim of complete LLM observability.

## Retained log identity

| File | Bytes | SHA-256 |
|---|---:|---|
| `native/native-run.json` | 246926 | `80e97ae974a4e08f809b844e092e855bfbc001e209d3d7d066b5eddee30b5897` |
| `native/native-rpc.jsonl` | 838356 | `f4cc34ac3fb3caaf70feccde5ab3701e820feff9923659d00d9f6ba250c1ea7c` |
| `native/native-bootstrap.jsonl` | 2306 | `321500d705f6a93fc70c419b30dbe66edac8a63c8c689673b85943ee88fc13c2` |

Source: `src/suiroai/integration/native.py` (`_Transport.record/send`, `execute`, paired command/file-change receipts); `src/suiroai/integration/native_profile.py` (`profile_overrides`, `verify_restrictions`, `sanitize`, `config_projection`, `project_message`). No code changes made for this inventory.
