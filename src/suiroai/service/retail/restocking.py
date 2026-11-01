"""Retail **restocking** rules, expressed as data for the generic engine.

Restocking is one problem type within the retail domain (see ``service/retail/__init__.py``), and
the first one built. The retail restocking business rules (docs/04-business-rules.md) live here as
a :class:`~suiroai.service.rules.RuleSet` — metric functions and flag predicates over a backend
order record — rather than inside the engine. The engine (``service/derive.py``) stays
domain-neutral; other retail problem types (pricing, assortment, promotions, …) add their own
rulesets alongside this one without touching the engine.

The thresholds below are the documented defaults and are parameterised via
:func:`build_restocking_ruleset`, so a deployment or workspace can supply its own numbers without
editing logic.

Honesty rules carried over: a metric returns ``None`` ("not enough data") when its inputs are
missing rather than guessing; flags that need data the backend order record does not carry are
declared as unavailable with what they need (they are not fabricated). The backend order row is
horizon-based and does not carry supplier identity, category, expiry, weekly pace, trend or
last-restock, so only the rules those real fields support are derivable today.
"""
from __future__ import annotations

from datetime import date

from suiroai.service.rules import FlagRule, MetricRule, RuleSet


# ---- documented defaults (overridable via build_ruleset) ----
DEFAULT_TARGET_COVER = 2.5          # docs/04 §4.1 THRESH, in cover units (weeks)
DEFAULT_DAYS_PER_COVER_UNIT = 7     # a "cover unit" is a week
DEFAULT_STOCK_OUT_THRESHOLD = 1.0   # cover below this (and nothing incoming) = stock-out risk
DEFAULT_SEVERITY_ORDER = ("act", "review", "watch")


def _horizon_days(order: dict):
    try:
        start = date.fromisoformat(order["forecast_horizon_start"])
        end = date.fromisoformat(order["forecast_horizon_end"])
    except (KeyError, TypeError, ValueError):
        return None
    span = (end - start).days + 1
    return span if span > 0 else None


def build_restocking_ruleset(*, target_cover: float = DEFAULT_TARGET_COVER,
                             days_per_cover_unit: int = DEFAULT_DAYS_PER_COVER_UNIT,
                             stock_out_threshold: float = DEFAULT_STOCK_OUT_THRESHOLD,
                             severity_order: tuple[str, ...] = DEFAULT_SEVERITY_ORDER) -> RuleSet:
    """Return the retail restocking ruleset, with overridable thresholds (none baked in)."""

    def cover(order, _metrics):
        """Weeks of cover at the forecast demand rate; None when not derivable (no guessing)."""
        on_hand = order.get("usable_on_hand_quantity")
        forecast = order.get("forecast_quantity")
        days = _horizon_days(order)
        if on_hand is None or forecast is None or days is None or forecast <= 0:
            return None
        daily = forecast / days
        if daily <= 0:
            return None
        return round(on_hand / daily / days_per_cover_unit, 2)

    def stock_out_risk(order, metrics):
        """§4.3: cover below threshold and nothing incoming. False when cover can't be computed."""
        c = metrics.get("cover")
        if c is None:
            return False
        incoming = order.get("eligible_receipt_quantity") or 0
        return c < stock_out_threshold and incoming == 0

    metrics = (
        MetricRule("cover", cover,
                   requires=("usable_on_hand_quantity", "forecast_quantity",
                             "forecast_horizon_start", "forecast_horizon_end"),
                   description="Cover units of stock at the forecast demand rate"),
        MetricRule("target_cover", lambda o, m: target_cover,
                   description="Configured target cover (constant from the ruleset)"),
    )

    flags = (
        # Derivable today from the order record:
        FlagRule("stock_out_risk", "act", fn=stock_out_risk,
                 description="Cover below threshold with nothing incoming (§4.3)"),
        # Declared but not derivable from the backend order record — reported as unavailable,
        # never fabricated. Each states the data that would unlock it.
        FlagRule("supplier_min_not_met", "act",
                 needs="a supplier identity with an aggregate minimum (backend extension, map §2.5)"),
        FlagRule("ordering_not_moving", "act",
                 needs="days-since-last-sale (not in the order record)"),
        FlagRule("tech_out_of_date", "act",
                 needs="product category and months-on-sale (not in the order record)"),
        FlagRule("expiry_risk", "act",
                 needs="expiry / sell-by dates (not in the order record)"),
        FlagRule("large_vs_usual_restock", "review",
                 needs="the previous restock quantity (not in the order record)"),
        FlagRule("not_moving", "watch",
                 needs="days-since-last-sale (not in the order record)"),
    )
    return RuleSet(metrics=metrics, flags=flags, severity_order=severity_order)


# The default retail restocking ruleset.
RETAIL_RESTOCKING_RULES = build_restocking_ruleset()
