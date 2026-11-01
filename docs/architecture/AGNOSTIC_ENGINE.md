# Architecture: agnostic engine, retail-chain focus

**Status:** architecture of record for the service layer · persisted so the design is not lost.

This records a design decision that reframes how the service layer (`src/suiroai/service/`) is
built, established through review. Read it alongside
[`docs/frontend-mapping/INTEGRATION_SPEC.md`](../frontend-mapping/INTEGRATION_SPEC.md) and
[`FRONTEND_TO_BACKEND_MAP.md`](../frontend-mapping/FRONTEND_TO_BACKEND_MAP.md).

## The decision

1. **The system is problem-agnostic.** The engine solves whatever problem it is given; it holds no
   domain knowledge. Business rules (metrics, thresholds, flags, severities) are **supplied as
   data**, never baked into engine code.

2. **The existing single-case backend is the demo, not the target.** The repository's governed
   pipeline (`contracts`, `parent`, `intake`, `modeling`, `replenishment`, `reporting`,
   `verification`) implements **one** historical retail restocking case. Its single-case
   constraints — the fixed 2025-11-30 temporal plan, the one-task boundary in `intake/roles.py`,
   the "no generic task router" note in `ARCHITECTURE.md` — describe *that demo*, not the system's
   ambition.

3. **Current focus is all of retail — the end-to-end chain.** Not a single problem, and not every
   domain on earth. Retail here spans the whole chain, suppliers included:

   ```
   demand → forecasting → replenishment/restocking → suppliers / procurement →
   inventory & stock health → pricing / markdown → assortment → fulfilment
   ```

   Restocking and suppliers are built first; the rest of the chain is anticipated by the structure.

## How it is realised in code

```
src/suiroai/service/
  rules.py                 # domain-neutral rule model: RuleSet, MetricRule, FlagRule (no domain terms)
  derive.py                # generic engine: evaluate a RuleSet against a record; no domain knowledge
  retail/                  # the retail-domain rule library — the end-to-end chain
    __init__.py            # RETAIL_PROBLEMS registry + RETAIL_CHAIN map (built vs planned stages)
    restocking.py          # restocking rules as data (cover, stock-out), thresholds overridable
    suppliers.py           # supplier/procurement rules as data (lead time, line minimums, on-order)
  orchestrator.py          # reads committed analysis evidence (demo path)
  views.py                 # record → frontend shapes
  store.py                 # store factory + fixture loader
```

- **Engine knows nothing about retail.** `derive.derive(record, ruleset)` evaluates whatever
  metrics and flags the `ruleset` declares. With `rules.EMPTY_RULES` it computes nothing, because
  the base system has no domain.
- **Retail is a supplied rule library.** `service/retail/` expresses the chain. Each stage is a
  problem *area* contributing one or more `RuleSet`s built from the generic model. Selecting an
  area is `retail.ruleset_for("restocking" | "suppliers")`; unknown areas raise rather than
  silently falling back.
- **Thresholds are parameters, not constants.** e.g. `build_restocking_ruleset(target_cover=…,
  stock_out_threshold=…)`, `build_supplier_ruleset(long_lead_days=…)`. Deployments/workspaces
  override without editing logic.
- **Honesty is structural.** A metric returns `None` ("not enough data") when inputs are missing,
  never a guess. A flag the backend record cannot substantiate is declared **unavailable** with the
  data it needs (e.g. supplier *aggregate* minimums need a backend extension — see map §2.5), never
  fabricated or silently dropped.

## Adding to the retail chain

To add a chain area (e.g. pricing/markdown): add `service/retail/<area>.py` with a
`build_<area>_ruleset(...)` returning a `RuleSet`, register it in `RETAIL_PROBLEMS` and mark it
`built` in `RETAIL_CHAIN`. **No engine change.** That property — new retail problems are new data,
not new engine code — is the point of the design.

## Deployment

Platform-agnostic by construction (no Mac-only assumptions; see the DSC-78/DSC-79 portability
work). Intended deployment target is OpenShift (Linux containers); macOS is a development option.
The macOS-gated native Codex/Data integration stays an optional dev adapter and is never on the
universal path.

## Relationship to the governed backend

The engine/rules layer sits **above** the governed pipeline: it consumes the pipeline's committed
records (e.g. `quantity_result` order rows) and applies the supplied ruleset to derive presentation
values. It does not replace the pipeline's own analytical governance (approval, verification,
immutable evidence), which remains authoritative for the numbers themselves.
