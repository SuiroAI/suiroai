# DSC-60: trace and repair the Codex/Data handoff

Tracking: [DSC-60](https://linear.app/gr3enarr0w/issue/DSC-60), [DSC-59](https://linear.app/gr3enarr0w/issue/DSC-59), [DSC-9](https://linear.app/gr3enarr0w/issue/DSC-9).

**Performance-success recording remains blocked.** This work fixes and examines the workflow that delegates analysis to Codex/Data. The local numerical reconstruction is bounded engineering validation of Data's claims, not a replacement production analyst or a new retail forecasting implementation.

## What the original calls actually contained

Start with [the historical call-chain index](trace/index.json), [context-check prompt](trace/current-process-outbound-prompt.txt), and [analysis prompt](trace/investigation-outbound-prompt.txt). These are the exposed stored outbound text, not a reconstruction from today's prompt builder. They link the original question, detector quotations and summary, exact input hashes, model/effort/plugin settings, native thread/turn IDs and original logs. [Observability limits](trace/native-observability.md) distinguish visible inputs/actions from hidden host/provider context and omitted tool output.

The question survived the original handoff, but the service appended the detector's derived summary and labelled the whole composite “Original question.” The detector correctly reported that recent months were mentioned without an exact quantity-setting rule. Ordering-policy parameters were not evidence of an incumbent. The four uploaded originals match the recording-index hashes; only the sales partition through November 30 reached analysis. The original sales hash is `520fa470...7707`; the released partition is `48238e68...a0b8`.

The original analysis prompt already required autonomous data investigation, honest comparisons, simple baseline distinctions, useful output, no analytical follow-ups, local non-LLM calculation assessment and separate AI build charges. It did **not** establish a persisted pre-score evaluation plan or a stable selection rule for a small/mixed improvement. Data's generated script selected by seven-day MAE, then its explanation justified retaining the seasonal method using better aggregate totals/RMSE despite worse later MAE. The final response disclosed that deterioration honestly. This is an observed task/selection-contract gap; it is not proof that a role label or prompt formatting causes better forecasts.

## Workflow changes

- Preserve the exact original question separately from manual answers, detector interpretation with quotations, and explicit continuation without an approach. Bind that context to the approved proposal digest.
- Send a structured role/objective/context/deliverable brief to genuine Data. Require an evaluation plan before scores, fair baseline and information boundaries, one declared primary selection metric, treatment of ties and plan revisions, horizon disclosure, and honest baseline selection when improvement is unsupported.
- For an authorized controlled comparison, carry an explicit controller contract through review, approval and Data. Its canonical digest binds target, baseline, metric, population, periods, horizon and selection. Edits revoke approval. Inspect declared adoption internally and retain plan bytes; an echoed contract is not proof that the code implements it.
- Trace both actual native calls before execution: exact prompt bytes/hash, input manifest, requested configuration and pinned skill identity. Complete the receipt with exposed configuration, outcome/thread/turn IDs and native log hashes. Keep traces outside the native evidence directory so its fresh-empty contract continues to pass.
- Keep ordinary user usefulness independent from the internal performance-recording gate. Product copy, uploader, context follow-up/Continue-without, explicit review/approval, December isolation, unrestricted healthy execution, standalone CSV and manually opened exact table-only HTML remain intact.

See [task construction details](../../../docs/demo/dsc60-task-construction.md). Tests traverse real service approval/native dispatch boundaries with injected transport and separately exercise native root validation; they do not certify model compliance.

## Experiments and independent review

Three distinct experiments are retained; do not combine their outcomes:

1. `scripts/dsc60_prompt_experiment.py` freezes historical/revised task construction with **the same additional evaluation controls in both arms**. Those controls fix the recorded target, six methods, baseline, origins, seven-day MAE and a 5%-in-both-development-periods stability rule. It is a conditional format comparison, not an exact historical-prompt replay. Both actual Data arms retained the baseline. Independent review found their 40,320 weekly target/prediction rows per arm agree with independent source reconstruction. Identical conditional forecasts do not show a prompt-driven accuracy gain.
2. `scripts/dsc60_trace_replay.py` replays the **exact exposed recorded detector and analysis prompts without an appendix**, alongside the revised analysis prompt on the same original released paths/context. Fresh sibling output/native directories preserve the original artifacts. The revised arm deliberately uses retained detector context, isolating task construction; this is not a fresh detected end-to-end browser run. Its new pre-dispatch receipts establish exact current outbound text. One stochastic replay cannot establish a unique internal cause or full hidden-context equality.

   [Retained exact-replay evidence](exact-replay/frozen-replay.json) shows the gap remained under structure alone: Data chose an 84-day baseline and coverage-horizon RMSE in its revised plan. Its small claimed gain belongs to that different development design, and is not improvement on the original seven-day MAE comparison. The exact original-prompt replay also chose different analytical details from the recording. Autonomous choices and stochastic runs cannot be compared as though the benchmark stayed fixed. The visible defect is a missing controlling comparison contract, not established loss of the user's words or proof that adding a role improves prediction.

3. `scripts/dsc60_workflow_replay.py` exercises the **actual service review → engineering approval → genuine backend/Data → CSV/HTML output** using [the fixed contract](trace/comparison-contract.json), the original four uploads and retained detector finding. [The service receipt](fixed-workflow/engineering-workflow-replay.json), [plan](fixed-workflow/output/evaluation_plan.json), [selection evidence](fixed-workflow/output/selection_evidence.json), [response](fixed-workflow/output/response.md), and [independent call-chain review](independent/fixed_workflow_review.json) establish observed adherence: exact contract transmitted, plan before score execution, unchanged baseline/primary metric/rule, and baseline retained. It completed with a useful illustrative list, without claiming improvement. This is engineering execution, not a new customer browser recording.

   The final plan-inspection helper was added after this run launched. Its [post-run inspection](fixed-workflow/postrun-plan-inspection.json) of the actual plan reports `recorded`, with `semantic_compliance_verified=false`; automated stage integration is covered by tests, not falsely claimed as live coverage in this run. Matching launch-source snapshots are retained. Independent review checks actual code/actions separately. One generated contract-hash assertion was added after the final scoring execution; full execution of that later assertion is not claimed.

The [independent review](independent/REVIEW.md) inspects methodology, calculations, calls and chronology without executing generated producer analysis as its verifier. Supporting local reproduction lives in [development evidence](development/README.md). The proposed 5% plus positive time-block uncertainty lower bound is an **engineering recording criterion**, not a customer business-value threshold, purchasing-cost function or savings claim. The both-development-periods experiment stability control is a separate rule. Neither was supplied by the merchant.

## Why recording is still blocked

The original 1.89% earlier MAE gain reversed to 5.99% worse later; October–November is development evidence. Arithmetic/table consistency cannot establish forecast superiority. Sparse recorded orders, final status knowledge and capture assumptions limit the meaning of those forecast scores. Aggregate seasonal totals can improve while local MAE worsens; do not state that seasonality universally failed to generalize or switch to a favorable metric.

Twelve retained demo sales releases contain no post-November-30 dates. That establishes isolation in those releases, not universal untouched status: the full-year original and prior QA were available. No December outcomes are evaluated here. Broader exposure evidence/custodian confirmation is still required, followed by the parent-required adopted frozen model/rule/code/dependency/forecast chain and independent one-shot evaluation. The development-only illustrative first-week freeze is explicitly rejected by the limited recording checklist and does not satisfy DSC-9 final acceptance. If December cannot be certified untouched, use genuinely fresh authorized future evidence; never relabel inspected months.

No recording, original-video verification, security-policy bypass, PR merge or parent closure was performed. The earlier completed browser session was preserved. A subsequent explicitly requested browser run on port 8504 is documented below. The unrelated untracked `report (1).html` remains untouched.

## Checks and remaining limits

Final source checks through `637f5cd`: **815 tests and 659 subtests passed** in the canonical `.venv`; the environment-contract configuration checks also passed. `git diff --check` passed. The independent reviewer accepts the scoped workflow/ordinary-baseline behavior; performance acceptance stays blocked.

The actual fixed-workflow response says “This analysis took about a second.” That measurement is the local non-LLM calculation, not whole AI-assisted wall time. Evidence is unchanged; the future prompt explicitly requires naming local calculation time, and the subsequent genuine browser run below verified that instruction in its emitted response. Metered AI build charges remain unknown. No purchasing savings are established.

At the user's subsequent explicit request, a new two-hour keep-awake assertion was started and verified at approximately 12:38 Eastern on October 20, expiring around 14:38. It is independent of the previous recording's expired assertion.


## Actual Streamlit browser run, October 20

At the user's request, source `637f5cd` was launched on port **8504** with the same fixed controller contract supplied by the trusted environment setting. The original short question and four files were entered through the actual browser. Ordinary native file selection worked without changing extension permissions. Task review was clicked once, the readable proposal was inspected, and approval was clicked once. Genuine context detection and Data analysis both completed. This closes the earlier UI-run gap; it does not change the performance gate.

See [the completed run](streamlit-run-2026-10-20/README.md), [call/UI index](streamlit-run-2026-10-20/run-index.json), and [independent workflow review](independent/streamlit-run-2026-10-20/REVIEW.md). The final live helper recorded exact contract adoption while explicitly leaving semantic verification false. Independent static inspection checked implementation adherence separately. The app returned the baseline with **873 illustrative units, 111 positive combinations, 225 zero orders and 56 early-shortage warnings**; these are this run's outputs, not the earlier recording's quantities.

The complete explanation including routine/AI cost separation was traversed. HTML was opened by an explicit click in a separate tab and scrolled, then the app was restored. All 336 rows × 18 cells, headers and row order match the emitted CSV independently. The separate explicit CSV click reached the ordinary Save dialog, after which Brave reported **“Blocked by your organization.”** No security setting was changed and no browser download is claimed. Screenshots document separate observations, not a continuous recording.
