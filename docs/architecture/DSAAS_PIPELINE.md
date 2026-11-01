# Architecture: DSaaS MVP — the 14-step working-demo flow

**Status:** architecture of record for the MVP. Supersedes the "rule engine / retail rule library"
framing (`AGNOSTIC_ENGINE.md`, `RETAIL_CHAIN_SPEC.md` — retired). Grounded in the Miro board
*"SuiroAI — Agent Architecture and Guardrail Review."*

## What the product is

Suiro is **data science as a service**. The customer, through an LLM, provides a problem and data;
the LLM reiterates its understanding; the customer validates; then the service does the data
science on the customer's data and delivers a result — ending in a **runnable customer app**.

## MVP scope (very small, on purpose)

The board's own summary: **"A build plan for a working demo: one parent, one coding task, one
execution pipeline, one humanizer and one usable customer app."** Singular everything. This is a
literal demo/MVP:

- one prepared demo dataset, **one** supported business problem;
- **no neural-network feature engineering**; the pipeline is simple;
- as few stages as possible to show the end-to-end flow and produce a runnable app.

## The main flow (14 steps)

Left to right, **every arrow is a handoff**. Each green main-flow step has a blue **guardrail**
above it (the invariant that must hold at that step). Clarifications or missing inputs return to
Understanding; the first handoff happens **only after the customer confirms**.

| # | Main-flow step | What happens | Guardrail |
| --- | --- | --- | --- |
| 1 | Customer starts | Upload CSV/Excel; describe one business question | Input scope: one prepared demo dataset, one supported problem |
| 2 | Parent + humanizer | Restate the goal in familiar language; check required data is present | Understanding: explicitly report missing data; no silent assumptions |
| 3 | Customer confirms | Confirm understanding; supply missing info if asked | First handoff: understanding signed off, required inputs available |
| 4 | Parent prepares one task | One pipeline specification: metric, splits, comparator, limits | Pipeline contract: context-aware cleaning, untouched holdout, agreed metric |
| 5 | Codex writes the code | Cleaning → model → app: code, configuration and tests only | Authoring boundary: Codex writes, runtime executes; limited deps |
| 6 | Parent approves the run | Inspect code and run contract; hand off to a separate environment | Run approval: review code before execution; bounded compute, permitted access |
| 7 | Runtime executes a stage | One pipeline, staged execution; return real artifacts and logs | Execution: train/transforms, folds, stage logic, artifacts and versions |
| 8 | Parent checks checkpoint | Verify results; resume next stage; only a complete pipeline advances | Checkpoint gates: stop on weak/invalid results; holdout never used to tune |
| 9 | Humanizer presents results | Final findings, benefits and limits; parent verifies numbers and visuals | Explanation: plain language, supported claims, no extra approval gate |
| 10 | Customer receives results | Plain-language report and charts; app delivery next, no reply gate | Results update: final validation passed; verified findings; preserve limitations |
| 11 | Runtime builds executable | Build from approved Codex code; one input→output; return artifacts | Build checks: approved code + frozen artifacts; platform parity; fresh-input tests |
| 12 | Customer receives app | Parent verifies app and instructions; deliver tested executable | Delivery checks: parent-verified executable + guide; no refitting; agreed platform |
| 13 | App runs on fresh inputs | Customer uploads and clicks Run; validate; apply the frozen model | New-input checks: expected schema/units/history; no refitting during prediction |
| 14 | Customer gets outputs | Readable business-purpose results; view/download; repeat as needed | Output fidelity: requested purpose and units; preserve limits; no inverted outputs |

**Execution loop (steps 7–8):** an accepted checkpoint resumes the next runtime stage; code errors
return to the **same bounded Codex task** (step 5), not to the customer.

## Map to the backend that exists

The five "actors" in the flow map to existing modules; the service layer wires them, it does not
re-implement them.

| Flow actor | Backend |
| --- | --- |
| Parent (guardrail controller, steps 2/4/6/8/12) | `parent/workflow.py` (`ParentWorkflow`) |
| Humanizer (steps 2 restate, 9 present) | `intake` humanizer + `reporting/drafts.py` |
| One coding task + runtime (steps 5/7/11) | `integration` (Codex/Data native adapter) + `modeling`/`preparation` stages |
| Pipeline stages (step 7) | `preparation → initial_baseline_evaluation → comparison_and_freeze → final_validation` |
| Contracts/evidence/checkpoints | `contracts` + the `ParentWorkflow` checkpoint gates |

Human-in-the-loop points are steps **3** (customer confirms understanding) and **10/12** (customer
receives results, then the app). The MVP drives this over the committed demo evidence; a live
Codex run is additive (and macOS-gated today — see the portability/native work).

## What the service/framework layer builds (MVP)

- **Intake**: upload one dataset + one business question; run the humanizer's **restate →
  customer-confirm** loop (steps 1–3).
- **Drive the one task/one pipeline** through the parent's approve → execute → checkpoint loop
  (steps 4–8), over demo evidence.
- **Present results** (steps 9–10) and **deliver the runnable app** (steps 11–14): build the
  executable from approved code, let the customer run it on fresh inputs, return outputs.

### Not in the MVP
- Neural-network feature engineering.
- Any authored domain rule library (the analysis is what the pipeline produces on the data).
- Multi-problem / multi-dataset; it is one of each.

## Forward plan (MVP, stdlib only, no new deps)

Resume the framework path scoped to these steps: a small HTTP service for steps 1–3 (upload +
understanding + confirm), driving the parent/pipeline for steps 4–10 over demo evidence, then the
app build + run for steps 11–14. No stage-06 NN work; no authored data science.
