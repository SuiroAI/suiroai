# DSC-10 component guard evidence

Evidence mode: **mock**. Initial base: user-selected `nightly` at `83f134fb7674de64d7f3a6b62f984bb6486ec81d`; the frozen-release follow-up incorporates nightly `1418220` (DSC-28). Contract: unchanged DSC-24 `0.1.0-draft.3`. All seven schema/validator/example snapshot hashes were checked against `docs/contracts/SNAPSHOT.json`. These results establish component behavior, not real retail analysis or integrated acceptance.

## Executed checks

From the DSC-10 worktree with Python 3.13. The existing application virtualenv supplies the locked `jsonschema` dependency; `PYTHONPATH=src` imports this worktree, not the foundation checkout.

```sh
PYTHONPATH=src /Users/ceverson/Development/SuiroAI/suiroai/.venv/bin/python -m unittest discover -s tests/parent -q
PYTHONPATH=src /Users/ceverson/Development/SuiroAI/suiroai/.venv/bin/python -m unittest discover -s tests/contracts -q
PYTHONPATH=src /Users/ceverson/Development/SuiroAI/suiroai/.venv/bin/python -m unittest discover -s tests/integration -q
PYTHONPATH=src /Users/ceverson/Development/SuiroAI/suiroai/.venv/bin/python -m unittest discover -s tests/modeling -q
git diff --check
```

| Suite | Actual result | Evidence limit |
| --- | --- | --- |
| Parent transition/permission/recovery/delivery | 56 tests passed | Real adapter and measured local artifact store, invented shared packets and mock host/reviewers; no native invocation. |
| Unchanged shared contracts | 77 tests passed | Structural, reference and declared-semantic guards; no analytical execution. |
| Existing integration component suite | 141 tests passed | Adapter/native protocol and isolation component regressions; no new customer or analytical acceptance inferred. |
| Existing modeling component suite | 69 tests passed | Frozen-artifact/analytical kernel component regressions; no genuine source analysis or parent/modeling runtime acceptance. |
| Snapshot integrity | 7 of 7 hashes matched | Shared contracts/examples were not changed. |
| Whitespace | Passed | Source/docs formatting only. |

## Frozen-release follow-up

The initial parent PR #6 had 45 passing parent tests. The DSC-28 owner subsequently identified missing immutable metadata in the final-validation allowlist. The follow-up adds 11 tests (56 parent checks total) for exact bundle/manifest/plan/rule/forecast-input release; forged selection, bindings or execution digest; unreviewed bundles; extra or duplicate-key payload content; canonical bytes; and denial of bundle/holdout references to every development stage. These checks use the agreed DSC-28 bundle format with explicitly invented evidence and the real adapter/store. They do not run an unseen evaluation.

A bundle must be cited in the adopted comparison checks, contain exactly the agreed envelope fields, and have canonical byte identity matching its parsed payload. Parent-decision evidence alone cannot authorize a bundle. The detached frozen manifest and plan/rule bytes must match the adopted selection and approved execution exactly. No model or feature fallback is introduced.

## Requirement-to-check evidence

| Guard | Tests / actual observed behavior |
| --- | --- |
| No execution before current explicit approval | Pending/silence waits; rejected approval returns to intake; unauthenticated consent and stale proposal bindings cannot start or dispatch. |
| Approval invalidation | Corrected proposal/new material input revoke approval and outstanding exact request permission; unchanged old approvals fail. |
| Run permissions | Full required action set enforced at start; one exact request and single-use permission; altered hashes, stale attempts/run IDs, expired requests and cancellation cannot advance. |
| Checkpoints and internal progress | Failed/unavailable preparation or verification checks and parent veto block progression; `take_response` is unavailable until exact verified final output. |
| Material clarification | A worker-authored hyperparameter question marked material is rejected by trusted review; a confirmed consequential unit fact returns to intake and revokes approval. |
| Chronology and freeze | Raw/holdout releases are denied to development; holdout requires freeze; altered threshold, forecast or a second-model packet cannot pass. |
| Distinct initial branches | Better proceeds; equal/worse pause for bounded internal review before LLM features; they do not become final holdout failures. |
| Bounded correction | A demonstrated scoring defect can pass a second evaluation with exact prior authorization and unchanged freeze. A second failed evaluation exhausts recovery and terminates without another model. |
| Five-domain failure review | Missing source/split/model/metric/runtime evidence prevents authorization; unresolved/model-tuning requests cannot authorize rechecks. Review count, stage attempts and time are enforced, including time consumed by the reviewer. |
| Honest terminal output | Confirmed measured failure and exhausted correction both reach an independently checked failure explanation with zero orders; runtime recheck failure uses the execution explanation path. |
| Predispatch and budget failures | Controller-owned typed receipts explicitly claim no native activity; cancellation/initial stop/analytical exhaustion can reach verified failure output within the original reserved remainder. |
| Delivery revocation and exhaustion | Cancellation revokes a report awaiting delivery. A failed verifier or exhausted verification allowance enters terminal `delivery_blocked`; it cannot reopen or deliver. |
| Independent check registration | A measured check-only record is retained as external evidence without delivery authority; the final reviewed proposal cites it and the exact report. |
| Mock isolation | Default real mode rejects mock chains; mock fixtures cannot dispatch DSC-26 `NativeHost`. |

Read-only review and adversarial-test subagents found gaps in action enforcement, deadline/review expiry, failure evidence/verification budgeting, cancellation and material-gap review. Those findings were repaired and covered by the passing suite. No issue status was changed from mock evidence.

## Consumer assumptions and remaining gates

See [transition/permission rules](README.md) and [owner coordination/integration blockers](COORDINATION.md). Trusted intake consent, content/chronology reviewers and independent evidence reviewers must replace the explicit mock callbacks. Complete genuine intake → approved packet → native adapter → preparation/modeling/quantity/report/verification acceptance remains unexecuted here. DSC-26's existing genuine isolated synthetic evidence is retained with its original scope.

The safe derived-development release for preparation and the native check-only verification transport require owner coordination; this branch does not bypass the pinned validator or expose raw December rows as a workaround. Restart restoration is deliberately unsupported: immutable event bytes and in-process pauses do not establish authenticated process-restart resume. MVP acceptance, recording and issue closure wait for genuine upstream outcomes and the acceptance owners.
