# DSC-59 product requirements

Authoritative user clarifications recorded October 19, 2026. These supersede contrary historical implementation notes. Tracking: https://linear.app/gr3enarr0w/issue/DSC-59; parent MVP: https://linear.app/gr3enarr0w/issue/DSC-9.

## User experience

- One generic area accepts multiple uploaded files. Intro: **Upload your data.** Question label: **What are you trying to solve for?**
- Review the proposed task in ordinary readable language, not raw JSON. Show the goal, files, intended result, material assumptions, and approval scope. Do not show a Technical details section or proposal ID anywhere in the product UI; retain identifiers internally.
- Users never need to provide or understand a data dictionary. Do not request or mention one in the product flow.
- After explicit approval, genuine ChatGPT Data inspects and analyzes the actual uploaded data and returns the actual downloadable output file. No fixtures substituted silently, mock success, or inventory-only endpoint.
- The restocking list is a separate downloadable data file in the same file format as the supplied inputs. The supplied example uses CSV, so deliver an importable restocking CSV with identifiers, reliable names, quantities and units. Keep the HTML report available through an **Open HTML report** link that opens a new browser tab; CSV remains a download. The plain-language explanation of findings and decisions also appears in the app response.
- Data is the data scientist and its report is the deliverable. Present it neutrally as Data's analysis/report. Do not show generic draft, unverified, or “independent verification has not been completed” disclaimers. Keep substantive methods, assumptions, measured results and relevant scientific limitations.

## Customer explanation

The app response uses concise layman’s terms, aiming for 150–250 words. Lead with the answer and practical actions. Explain why the selected model or approach helps compared with the previous approach when one was actually supplied and evaluated; otherwise compare against a clearly identified simple baseline. Use real comparisons and explain small, mixed or absent gains honestly. Do not invent an incumbent or claim a method is better without evidence.

Include a basic estimate of the cost to run the approach, with workload/frequency, currency and assumptions when supported by actual usage and applicable pricing. Distinguish ongoing use from this analysis run. If the necessary usage, pricing or deployment information is absent, say that the cost cannot be estimated from the available information. Never invent dollar amounts or call it free. Keep detailed methods, diagnostics and audit material in the HTML report rather than the main app response. The HTML may retain technical language.

## Data owns analytical decisions

Data acts as a data scientist. It infers structure, meanings, relationships and appropriate analysis from the files and requested goal. It investigates nulls, missing values/dates, duplicates, returns and statuses; chooses suitable treatments (for example preserving, excluding, imputing or modeling missing values); checks their effect; and uses supported methods, assumptions and sensitivity analysis to produce the best useful result. The application must not impose unresolved analytical-policy or metadata prerequisites before Data can investigate.

Do not ask the user follow-up questions about cleaning, business interpretation, or analytical uncertainty. Data resolves these from available evidence. If some requested conclusions cannot be supported, return useful supported findings and explain the evidenced limits in the output. Do not fabricate facts, coverage, performance or verification. Limitations belong in Data's reasoning and result; their existence alone is not an application-side reason to stop.

## Execution and acceptance

- No overall elapsed-time execution limit. Let healthy analysis take as long as needed; monitor actual failures, process/transport termination and user cancellation. Individual control-request responsiveness checks are not a deadline on model analysis.
- Material input changes revoke stale approval/results. Reruns, repeated clicks and downloads must not repeat execution or bypass current consent.
- The supplied November 30 retail example must preserve its December sales holdout boundary while allowing Data to choose development methods.
- Run the actual supplied example through the visible app and download its file before closure. Unit tests and preflight checks alone are insufficient.
- Keep generated-output provenance accurate. Do not call a Data-generated file independently verified without genuine verification evidence.
- Commit implementation, useful multiline Python module explanations, documentation, tests and reviewable visual/run evidence to SuiroAI/suiroai. Use GPT-6.1 medium subagents as requested.
- Keep DSC-59 and parent acceptance gates open until required real evidence passes. Record the precise result and remaining work in Linear.

## Verification checks

1. The initial UI has the exact generic copy and one multiple-file upload widget.
2. The review is readable and approves the actual Data scope.
3. No user-facing requirement asks for metadata, cleaning decisions or follow-up answers.
4. Approval reaches genuine Data with exact permitted file bytes and original question.
5. Data handles missingness and analytical choices autonomously and returns the supported result.
6. Healthy analysis is not interrupted by an overall elapsed-time deadline; failures/cancellation still work.
7. The standalone restocking CSV downloads and the demo HTML report opens in a separate browser tab, with both matching their stored output artifacts byte-for-byte. Plain-language findings and explanation also appear in the app, using neutral result language without generic verification disclaimers.
8. The real visible example, outcome, input/output hashes, tested revision and screenshots are retained.
