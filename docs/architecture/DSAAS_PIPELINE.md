# Architecture: data science as a service (DSaaS) pipeline

**Status:** architecture of record. Supersedes the "rule engine / retail rule library" framing in
`AGNOSTIC_ENGINE.md` and `RETAIL_CHAIN_SPEC.md` (both to be retired — see "Correction" below).

Grounded in the Miro board *"SuiroAI — Agent Architecture and Guardrail Review."*

## What the product is

Suiro is **data science as a service**. The product is the **framework that runs data science on a
customer's data**, not a library of pre-written analyses. Concretely:

1. The **customer, through an LLM, provides a problem and data.**
2. The **LLM evaluates it and reiterates its understanding back to the customer.**
3. The **customer validates** that understanding.
4. Only then does the **data-science-as-a-service run all the data science** on the customer's data
   and deliver results.

The actual analysis (cleanup, EDA, features, models, validation) is produced **per customer, per
upload** by the pipeline — it is **not** shipped as domain formulas. We build the framework; the
data science happens when customers provide data.

## Current scope: a simple demo / MVP

Right now we build a **very simple version** of this — a literal demo/MVP, **not** the full
pipeline. In particular there is **no neural-network feature engineering** (Miro stage 06 is out of
scope for the MVP). The MVP demonstrates the DSaaS flow end to end with the minimum stages:

> customer provides data + problem → LLM understanding → **customer validates** →
> the service runs the (simple) data science → results delivered.

Heavy ML, NN feature engineering, and the broader chain are **future**, not now.

## The pipeline (Miro 10 stages → backend)

The board lays out ten stages, corresponding to the governed pipeline in `src/suiroai/`. The
**MVP scope** column marks what the simple demo includes.

| # | Miro stage | Backend stage / module | MVP |
| --- | --- | --- | --- |
| 01 | Input, understanding and validation | `intake` (understanding → proposal → **reiterate** → customer **approval/validation**) | ✅ in |
| 02 | Data cleanup | `preparation` | ✅ in (simple) |
| 03 | Exploratory data analysis | `preparation` | ✅ in (simple) |
| 04 | Initial feature engineering | `preparation` | ✅ in (simple) |
| 05 | Initial baseline comparison + customer understanding | `initial_baseline_evaluation` | ✅ in |
| 06 | Neural-network feature engineering | `llm_features` | ❌ **out (MVP)** |
| 07 | Model comparison and feature selection | `comparison_and_freeze` | ✅ in (baseline models) |
| 08 | Final model validation on unseen data | `final_validation` | ✅ in |
| 09 | Customer results presentation | `recommendations` / `reporting` | ✅ in |
| 10 | Final delivery and runnable customer deliverable | `output_verification` + delivery | ✅ in |

Stages 01 and 05 are the human-in-the-loop points: the LLM reiterates understanding and the
customer validates. The `ParentWorkflow` (`parent/workflow.py`) is the guardrail controller that
gates these transitions and keeps evidence immutable. For the MVP, the service drives this over the
committed demo evidence; swapping in a live run is additive.

## What the framework/service layer builds (and does not)

**Builds (framework):**
- Data + problem **intake** (upload, the LLM understanding, reiteration to the customer, validation).
- **Driving the pipeline** over the customer's data through the ten stages, with the guardrails.
- **Delivering results** (stage 09/10) to the frontend and as a runnable deliverable.
- The HTTP/service surface, events and auth around all of the above.

**Does not build (this is the data science, done by the pipeline on customer data):**
- Pre-written cleanup/EDA/feature/model/analysis rules for any domain.
- A shipped "retail rule library" of metrics/flags/thresholds.

## Correction to earlier service-layer work

Earlier service PRs introduced a generic **rule engine** (`service/derive.py`, `service/rules.py`)
and a **retail rule library** (`service/retail/restocking.py`, `suppliers.py`), plus a chain-area
spec. Under the DSaaS framing these are a **misdirection**: they pre-author data-science rules
rather than letting the pipeline do the analysis on customer data. They are therefore retired. The
genuinely useful framework plumbing is kept:

- **Keep:** `service/store.py` (evidence store), `service/orchestrator.py` (drive/read a run),
  `service/views.py` (results → frontend).
- **Retire:** `service/derive.py`, `service/rules.py`, `service/retail/**`, `AGNOSTIC_ENGINE.md`,
  `RETAIL_CHAIN_SPEC.md`.

The "agnostic" property is real but is delivered by the **pipeline running on whatever data/problem
a customer supplies**, not by a rule-evaluation engine we ship.

## Forward plan (MVP)

Resume the framework path with the **simple demo** scope: a stdlib HTTP service that lets a customer
upload data and a problem, runs the LLM understanding + customer-validation loop (stage 01), drives
the pipeline over the demo evidence, and returns the presentation and deliverable (stages 09/10).
No neural-network feature engineering (stage 06). No domain data-science authored by us — the
analysis is what the pipeline does on the customer's data.
