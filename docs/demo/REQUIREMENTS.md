# DSC-59 product requirements

Authoritative user clarifications recorded October 19, 2026. These supersede contrary historical implementation notes. Tracking: https://linear.app/gr3enarr0w/issue/DSC-59; parent MVP: https://linear.app/gr3enarr0w/issue/DSC-9.

## User experience

- One generic area accepts multiple uploaded files. Intro: **Upload your data.** Question label: **What are you trying to solve for?**
- On **Review task**, automatically check the question and uploaded contents for a description of the current approach. If one is already described, proceed to the readable review without asking the user to confirm its presence or repeat it. A policy filename, column names or operational constraints alone do not establish how the business actually works today. If the approach is missing, ask **How do you do this now?** and show **Continue without a current approach**. Accept an explicit statement that no current approach exists; never invent one or demand a file. Bind the detected context, supplied answer or explicit continuation without an approach to the exact reviewed inputs. Changing those inputs or that answer invalidates approval/results. This business-context question is the explicit exception to autonomous analytical decision-making. The preapproval check only establishes whether context was supplied; analytical investigation still requires explicit approval.
- Review the proposed task in ordinary readable language, not raw JSON. Show the goal, files, intended result, material assumptions, and approval scope. Do not show a Technical details section or proposal ID anywhere in the product UI; retain identifiers internally.
- Users never need to provide or understand a data dictionary. Do not request or mention one in the product flow.
- After explicit approval, genuine ChatGPT Data inspects and analyzes the actual uploaded data and returns the actual downloadable output file. No fixtures substituted silently, mock success, or inventory-only endpoint.
- The main app window contains only the plain-language explanation and file controls. Do not embed the HTML table there. The HTML file is the separate preview, opened in a new tab only by an explicit click; recording/check automation must not automatically open it by default.
- Do not automatically click or start a CSV download when analysis finishes, during rerenders, or in the default recording/check flow. The user explicitly chooses the download button; clicking it must not rerun analysis. CSV-download verification is a separate opt-in action.
- The restocking list is a separate downloadable data file in the same file format as the supplied inputs. The supplied example uses CSV, so deliver an importable restocking CSV with identifiers, reliable names, quantities and units. The **View restocking list** link opens a table-only HTML rendering of the exact CSV in a new tab for demo recording. It is not a narrative report; CSV remains a download. The plain-language explanation of findings and decisions also appears in the app response.
- Data is the data scientist and its report is the deliverable. Present it neutrally as Data's analysis/report. Do not show generic draft, unverified, or “independent verification has not been completed” disclaimers. Keep substantive methods, assumptions, measured results and relevant scientific limitations.

## Customer explanation

The app response uses concise layman’s terms, aiming for 150–250 words. Lead with the answer and practical actions. Explain why the selected model or approach helps compared with the previous approach when one was actually supplied and evaluated; otherwise, after asking about the current process, compare against a clearly identified simple baseline. Use real comparisons and explain small, mixed or absent gains honestly. Do not invent an incumbent or claim a method is better without evidence.

Include a basic estimate of the cost to run the approach, with workload/frequency, currency and assumptions when supported by actual usage and applicable pricing. Distinguish ongoing use from this analysis run. The delivered forecasting/decision model is non-LLM: routine calculations must not require ChatGPT or other language-model calls; AI may build and explain it during analysis. For that selected model, assess the actual code, dependencies, data size and workload: explain whether routine runs can use an ordinary local computer and whether a paid model API is needed. When supported, explain that local runs need no paid model service, while computer/electricity costs still exist. Give a supported estimate or range with assumptions when possible; otherwise give the practical local-computer assessment or the specific unknown preventing it. Do not confuse routine model compute with AI-assisted analysis/build charges. Missing AI usage/pricing may prevent estimating that separate build cost without preventing the local-running assessment. Never invent dollar amounts or call it free. All explanation belongs in the same app window, entirely in everyday terms for a retail business owner. Keep detailed diagnostics and audit material internal. HTML contains only the CSV headers, rows and exact cell values: no findings, metric cards, extra summaries, methods, comparisons, costs or limitations. The app builds it deterministically from the CSV; Data does not author a separate HTML report.

## Data owns analytical decisions

Data acts as a data scientist. It infers structure, meanings, relationships and appropriate analysis from the files and requested goal. It investigates nulls, missing values/dates, duplicates, returns and statuses; chooses suitable treatments (for example preserving, excluding, imputing or modeling missing values); checks their effect; and uses supported methods, assumptions and sensitivity analysis to produce the best useful result. The application must not impose unresolved analytical-policy or metadata prerequisites before Data can investigate.

Do not ask the user follow-up questions about cleaning, business interpretation, or analytical uncertainty. Data resolves these from available evidence. If some requested conclusions cannot be supported, return useful supported findings and explain the evidenced limits in the output. Do not fabricate facts, coverage, performance or verification. Limitations belong in Data's reasoning and result; their existence alone is not an application-side reason to stop.

## Execution and acceptance

- No overall elapsed-time execution limit. Let healthy analysis take as long as needed; monitor actual failures, process/transport termination and user cancellation. Individual control-request responsiveness checks are not a deadline on model analysis.
- Material input changes revoke stale approval/results and context detection. A detection result from an older input revision cannot populate the current review. Reruns and repeated review clicks on unchanged inputs reuse the resolved context; they must not repeat analysis or bypass current consent. Downloads must not execute analysis.
- The supplied November 30 retail example must preserve its December sales holdout boundary while allowing Data to choose development methods.
- Run the actual supplied example through the visible app and download its file before closure. Unit tests and preflight checks alone are insufficient.
- Keep generated-output provenance accurate. Do not call a Data-generated file independently verified without genuine verification evidence.
- Commit implementation, useful multiline Python module explanations, documentation, tests and reviewable visual/run evidence to SuiroAI/suiroai. Use GPT-6.1 medium subagents as requested.
- Keep DSC-59 and parent acceptance gates open until required real evidence passes. Record the precise result and remaining work in Linear.

## Verification checks

1. The initial UI has the exact generic copy and one multiple-file upload widget.
2. The review is readable and approves the actual Data scope.
3. No user-facing requirement asks for metadata or cleaning decisions. Current-process context already described in the question or uploaded contents is detected automatically, without a confirmation question. Only missing context triggers **How do you do this now?**, with **Continue without a current approach** available. Explicitly absent approaches and policy-only uploads are handled accurately; the context check cannot start analytical investigation before approval.
4. Approval reaches genuine Data with exact permitted file bytes and original question.
5. Data handles missingness and analytical choices autonomously and returns the supported result.
6. Healthy analysis is not interrupted by an overall elapsed-time deadline; failures/cancellation still work.
7. The standalone restocking CSV downloads and the table-only CSV preview opens in a separate browser tab, with both matching their stored output artifacts byte-for-byte. Plain-language findings and explanation also appear in the app, using neutral result language without generic verification disclaimers.
8. The real visible example, outcome, input/output hashes, tested revision and screenshots are retained.

## DSC-60 internal tracing and comparison

Trace the exact native detector and analysis inputs before dispatch, then retain exposed model settings, input identities, thread/turn IDs, outcomes and native-log hashes. Preserve the original question separately from detector interpretations and manual process context. Hidden provider/system context is not asserted to be observable.

Data declares a comparison plan before scores. A controller-supplied engineering comparison contract, when present, is bound to approval and keeps target, baseline, metric, periods, population, horizon and selection fixed. Changing that contract revokes approval/results. Declared plan adoption is inspected internally and does not establish semantic compliance or improvement. Normal analysis remains useful without passing a recording gate, and these internal checks add no customer-facing obstacle or generic warnings.

Before a performance-success recording, independently establish meaningful improvement under the fixed comparison on genuinely untouched outcomes and satisfy the parent frozen-artifact requirements. Inspected development gains, changing the comparison, task-format improvements and completed execution cannot pass that gate. See [task construction and tracing](dsc60-task-construction.md) and [retained DSC-60 evidence](../../evidence/demo/dsc60-debug-2026-10-20/README.md).

## Demo scenario presentation — latest user clarification

For the local recorded demonstration, roleplay the supplied stock, incoming deliveries and ordering rules as the business's operating inputs. Show the resulting recommendation and useful actions without synthetic/illustrative replacement-data warnings or provenance-only flags in newly generated customer CSVs. Keep raw files, source provenance, synthetic classifications and engineering checks unchanged internally; do not claim independently verified real stock. This presentation instruction does not change forecast selection, fair comparisons, evaluation results or permit borrowed gains/savings claims. It supersedes earlier mandatory customer warnings about synthetic operating inputs. No new customer control or analytical follow-up is required.

## Weekly manual-process automation — latest user clarification

The core goal is to automate recurring restocking hand calculations with the supplied inputs/rules and produce the actionable list, not lead with a model-performance lecture. Deliver the actually selected non-LLM routine with configurable input paths, planning date and output, plus simple usage and actual local routine measurements. Keep the demonstration at November 30 with reserved outcomes isolated. Future scheduling can be explained as an optional setup step with ChatGPT assistance; do not claim a schedule or integration is installed, ask new customer questions, or invent manual-time/money savings. Supporting forecast comparisons remain fair, measured and brief in the customer explanation.

The October 20 recording correction makes automating manual weekly restocking the main customer outcome. Explain the ready list, repeated hand calculations replaced, priority items, measured weekly calculation time and supported scheduling option in ordinary words. Forecast comparisons remain honest supporting checks; do not turn the summary into a model-performance or audit report. Treat supplied stock/deliveries/rules as the roleplayed business inputs, without customer-facing synthetic-data replacement warnings. Keep actual source provenance internal.

Capture numeric usage from the actual intake, analysis and writing calls. After the writer completes, append a controller-calculated estimate at cited published standard API rates, including the writer's own usage; this is an API-equivalent estimate, not an authenticated bill. Retain original writer bytes and the separate published text. Do not say costs cannot be estimated when usage is available, imply a one-time build fee, claim automatic scheduling already exists, or add an electricity/hosting disclaimer. Missing measurements must not be fabricated.
