# Automatic current-process detection

Implementation:54a7a42. Updated local intake: http://localhost:8503/ . The completed earlier analysis stays on port8502.

Review task automatically inspects the original question and all uploaded CSV contents for an explicitly described current business process. It does not infer that process from sales patterns, filenames or operational policy parameters. Found context proceeds directly to readable review. Missing context shows “How do you do this now?” and “Continue without a current approach.” Explicit absence also proceeds without an invented incumbent. No analytical execution occurs during context inspection.

The exact question, uploaded bytes, detected context and explicit answer/continuation are bound to the reviewed task. Changed inputs revoke approval/results and cannot inherit an old typed answer. Repeated reviews reuse context; stale/interrupted/failed inspections do not publish approval or become invented missing context.

## Verification

- Full regression774passed +659subtests. Demo-specific130checks pass, including native detector contract/quotes/December isolation, real service context/consent transitions, stale/error/inflight/retry behavior and actual Streamlit widget reruns.
- Two genuine NativeHost checks used only authored nonsensitive synthetic CSVs, with no injected detector/host/backend: an uploaded note was detected with an exact source quote; sales/policy parameters alone produced missing context, and explicit Continue reached review. No analysis or approval ran. Exact inputs and redacted native provenance are retained in results.json.
- intake.jpg shows the actual revised page with the manual source selector removed. This is not a claimed new full retail-analysis run or continuous recording.
- Subagents: GPT-6.1-Sol medium detector implementation and independent context-flow review/tests. No confirmed consent bugs remained after review; strict historical CSV/date support follows the existing demo boundary.

## Live-check limitation

A first attempt with the supplied sales files could not start NativeHost within the sandbox. Automatic approval review rejected normal-permission execution because it considered the supplied sales payload insufficiently authorized for transmission to the native model destination. No rejected transmission or policy bypass occurred. sandbox-attempt.json and runtime-blocker.json retain this outcome. The safer live checks used only explicitly synthetic literal examples and were approved and completed. No private-file live check or new retail analysis with this update is claimed.

To reproduce the controlled live checks from the application checkout (uses genuine authenticated OpenAI native model calls):

    .venv/bin/python evidence/demo/dsc59-autodetect-2026-10-19/run_context_checks.py

These are scoped context-detection checks. Prior CSV browser-policy blocker and broader frozen-holdout/continuous-recording milestone gates remain separate and open.
