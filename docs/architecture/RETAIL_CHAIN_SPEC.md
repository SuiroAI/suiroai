# Retail chain spec — rule areas end to end

**Status:** spec for review · drives the build-out of `src/suiroai/service/retail/`.

Companion to [`AGNOSTIC_ENGINE.md`](./AGNOSTIC_ENGINE.md). That doc sets the design (generic engine,
rules as data, retail as a supplied library). This spec defines **every area of the retail chain**
as a ruleset to build, so the areas can be implemented one PR at a time against a fixed plan.

The engine is unchanged by any of this: each area is a `RuleSet` of `MetricRule`s and `FlagRule`s
(`service/rules.py`) registered in `service/retail/`. Nothing here is baked into the engine.

## Ground truth: fields available today

Every area's rules read a backend order record (`quantity_result.orders[]`). The fields that exist
**now** (verified against the committed fixtures) are:

```
key{source_namespace,product_id,store_id}, quantity_unit,
forecast_quantity, forecast_horizon_start, forecast_horizon_end,
usable_on_hand_quantity, on_order_summary_quantity, eligible_receipt_quantity,
supplier_lead_calendar_days, review_period_calendar_days,
safety_stock_quantity, order_multiple, minimum_positive_order_quantity,
raw_order_need, rounded_order_quantity, approved_order_quantity
```

Honesty rule for every area: compute a metric from these fields or return `None` ("not enough
data"); declare a flag that needs absent data as **unavailable with what it needs** — never
fabricate. "Needs data" below means a field the order record does not yet carry (a backend
extension or an additional uploaded file).

## Chain overview

```
demand → forecasting → restocking → suppliers/procurement →
inventory health → pricing/markdown → assortment → fulfilment
```

| Area | Key | Status | Build order |
| --- | --- | --- | --- |
| Demand | `demand` | planned | DSC-81 |
| Forecasting | `forecasting` | planned | DSC-82 |
| Restocking | `restocking` | **built** (DSC-73) | — |
| Suppliers / procurement | `suppliers` | **built** (DSC-73) | — |
| Inventory health | `inventory_health` | planned | DSC-83 |
| Pricing / markdown | `pricing_markdown` | planned | DSC-84 |
| Assortment | `assortment` | planned | DSC-85 |
| Fulfilment | `fulfilment` | planned | DSC-86 |

Each planned area ships as its own PR (ruleset module + registry entry + `RETAIL_CHAIN` status →
`built` + tests), stacked after this spec. Build order groups the readily-derivable areas first.

---

## Area specs

Each area lists **metrics** (derived values), **derivable flags** (computable from today's fields),
and **declared-unavailable flags** (need data; stated, not fabricated). Thresholds are parameters
on a `build_<area>_ruleset(...)` factory — overridable, never baked in.

### Demand (`demand`) — DSC-81
How much is actually selling and how volatile it is.
- **Metrics:** `daily_demand` = forecast_quantity ÷ horizon days (proxy until actuals upload);
  `demand_per_cover_unit`.
- **Derivable flags:** `zero_forecast` (forecast_quantity == 0).
- **Needs data:** `demand_spike`, `demand_drop`, `intermittent_demand`, `trend_up/down` — need
  historical actual sales by period (not in the order record; from the sales file/forecast series).

### Forecasting (`forecasting`) — DSC-82
Quality and confidence of the forecast feeding the chain.
- **Metrics:** `horizon_days`; `forecast_total` (forecast_quantity over the horizon).
- **Derivable flags:** `short_horizon` (horizon below a configurable minimum days).
- **Needs data:** `low_forecast_accuracy`, `wide_prediction_interval`, `model_drift` — need the
  model's held-out error / interval metrics (produced by `modeling`, not on the order row).

### Inventory health (`inventory_health`) — DSC-83
Is on-hand stock healthy: enough, too much, or stuck.
- **Metrics:** `cover` (reuse the restocking cover primitive); `weeks_of_supply`;
  `excess_units` = max(0, on_hand − target cover demand).
- **Derivable flags:** `overstock` (cover above a configurable high threshold);
  `understock` (cover below a low threshold); `dead_stock_candidate` (on_hand > 0 and
  forecast_quantity == 0 over the horizon).
- **Needs data:** `not_moving` / `expiry_risk` / `going_out_of_date` — need days-since-last-sale,
  expiry dates, category/months-on-sale (not in the order record).

### Pricing / markdown (`pricing_markdown`) — DSC-84
When stock should be discounted to clear.
- **Metrics:** `clearance_pressure` = excess_units ÷ max(1, daily_demand) (how long excess takes to
  sell at current pace).
- **Derivable flags:** `markdown_candidate` (overstock **and** clearance_pressure above a
  configurable horizon).
- **Needs data:** `margin_erosion`, `price_vs_competitor`, `elasticity_opportunity` — need unit
  cost, competitor prices, price-change history (not in the order record).

### Assortment (`assortment`) — DSC-85
Which items earn their place.
- **Derivable flags:** `no_demand_sku` (forecast_quantity == 0 and on_hand == 0 — nothing selling,
  nothing held).
- **Needs data:** `range_overlap`, `long_tail_low_contribution`, `category_gap` — need revenue
  share, category structure, cross-product data (not in the order record).

### Fulfilment (`fulfilment`) — DSC-86
Will stock be where it's needed in time.
- **Metrics:** `arrival_window_days` = supplier_lead + review (reuse suppliers primitive);
  `cover_vs_lead` = cover ÷ (arrival_window in cover units).
- **Derivable flags:** `stockout_before_arrival` (cover_vs_lead < 1 — runs out before replenishment
  lands); `nothing_inbound` (on_order == 0 and eligible_receipts == 0).
- **Needs data:** `store_transfer_opportunity`, `split_shipment_risk` — need multi-store on-hand
  and transfer data (the order record is per product-store; cross-store needs the full set).

---

## Cross-area notes

- **Shared primitives.** `cover`, `daily_demand`, `arrival_window_days` recur. They live as small
  helpers reused across area modules so the rules stay consistent (e.g. inventory health and
  fulfilment both use `cover`). No duplication of thresholds.
- **Severity tiers** stay the chain-wide `("act","review","watch")` unless an area overrides.
- **Selection.** `retail.ruleset_for(area)` already raises on unknown areas; each new area just
  registers itself. A caller can also compose areas (e.g. run restocking + inventory_health + 
  fulfilment over the same order set) — the engine evaluates each ruleset independently.
- **Multi-store rules** (assortment overlap, fulfilment transfers) need the whole order set, not a
  single row. Those are declared `needs data` now; implementing them is a follow-on once the
  service exposes the full order collection to a ruleset (a set-level rule variant), tracked
  separately.

## Acceptance for each area PR

1. Ruleset builds via `build_<area>_ruleset(...)` with overridable thresholds.
2. Registered in `RETAIL_PROBLEMS`; `RETAIL_CHAIN` status flips to `built`.
3. Every derivable metric/flag has a unit test over a representative order row.
4. Every `needs data` flag is asserted present in `unavailable` with a non-empty `needs`.
5. No engine change; no new runtime dependency.

---

*Build order: demand → forecasting → inventory_health → pricing_markdown → assortment →
fulfilment. After the areas, resume the API path (A-PR5–8) so the chain is reachable end to end.*
