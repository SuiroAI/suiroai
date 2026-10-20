# Final recorded call chain

`index.json` links the final recorded context-inspection call to the final analysis call, with exact outbound prompts, original question, detector evidence and source hashes. It extracts sent `turn/start` text from the original native RPC logs without changing it. Original input files remain in place and are referenced by hashes; no CSV contents or transaction rows are copied.

The earlier missing-context inspection in the same session belongs to another question and is not substituted for this final pair. Model/effort/plugin values are exposed requests and native receipts; hidden/system context is unknown. These historical calls predate the structured-task changes and the new call-trace receipt.

[DSC-60](https://linear.app/gr3enarr0w/issue/DSC-60)

Historical RPC events were stored through the existing projection/sanitization layer. These prompt hashes identify the exposed stored text; they do not establish pre-sanitization byte identity or knowledge of complete model context. New live call receipts capture exact outbound prompt bytes before native dispatch.
