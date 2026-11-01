"""Retail **supplier / procurement** rules, expressed as data for the generic engine.

Suppliers are part of the end-to-end retail chain (see ``service/retail/__init__.py``), and one of
the first areas built alongside restocking. These rules operate on the same backend order record,
which carries the supplier-facing fields the governed pipeline computes per product-store:
``supplier_lead_calendar_days``, ``review_period_calendar_days``, ``order_multiple``,
``minimum_positive_order_quantity``, ``on_order_summary_quantity`` and ``eligible_receipt_quantity``.

What is derivable today (from those real fields):
- lead-time exposure: how many days of demand are at risk while an order is in transit;
- order-feasibility: whether the ordered quantity honours the line's order multiple and minimum;
- in-transit coverage: whether anything is already on order.

What is **not** derivable from the order record and is declared as unavailable (needs a backend
extension, see map §2.5): a supplier *identity* and supplier-level *aggregate* minimums across
stores, lead-time reliability history, and price/terms. These are not fabricated.

Thresholds are parameterised via :func:`build_supplier_ruleset`; nothing is baked into the engine.
"""
from __future__ import annotations

from suiroai.service.rules import FlagRule, MetricRule, RuleSet


DEFAULT_LONG_LEAD_DAYS = 14          # lead time at or above this is flagged as long
DEFAULT_SEVERITY_ORDER = ("act", "review", "watch")


def build_supplier_ruleset(*, long_lead_days: int = DEFAULT_LONG_LEAD_DAYS,
                           severity_order: tuple[str, ...] = DEFAULT_SEVERITY_ORDER) -> RuleSet:
    """Return the retail supplier/procurement ruleset, with overridable thresholds (none baked in)."""

    def lead_time_days(order, _metrics):
        v = order.get("supplier_lead_calendar_days")
        return v if isinstance(v, (int, float)) and v >= 0 else None

    def lead_plus_review_days(order, metrics):
        lead = metrics.get("lead_time_days")
        review = order.get("review_period_calendar_days")
        if lead is None or not isinstance(review, (int, float)) or review < 0:
            return None
        return lead + review

    def on_order_quantity(order, _metrics):
        v = order.get("on_order_summary_quantity")
        return v if isinstance(v, (int, float)) and v >= 0 else None

    def ordered_qty(order):
        qty = order.get("approved_order_quantity")
        return qty if qty is not None else order.get("rounded_order_quantity")

    def below_line_minimum(order, _metrics):
        """§ order feasibility: a positive order below the line's minimum order quantity."""
        qty = ordered_qty(order)
        minimum = order.get("minimum_positive_order_quantity")
        if qty is None or minimum is None or qty <= 0:
            return False
        return qty < minimum

    def not_order_multiple(order, _metrics):
        """A positive order that is not a whole multiple of the supplier's order multiple."""
        qty = ordered_qty(order)
        multiple = order.get("order_multiple")
        if qty is None or not multiple or qty <= 0:
            return False
        return qty % multiple != 0

    def long_lead_time(order, metrics):
        lead = metrics.get("lead_time_days")
        return lead is not None and lead >= long_lead_days

    def nothing_on_order(order, metrics):
        oo = metrics.get("on_order_quantity")
        return oo is not None and oo == 0

    metrics = (
        MetricRule("lead_time_days", lead_time_days,
                   requires=("supplier_lead_calendar_days",),
                   description="Supplier lead time in calendar days"),
        MetricRule("lead_plus_review_days", lead_plus_review_days,
                   requires=("supplier_lead_calendar_days", "review_period_calendar_days"),
                   description="Demand window to cover while an order is placed and in transit"),
        MetricRule("on_order_quantity", on_order_quantity,
                   requires=("on_order_summary_quantity",),
                   description="Units already on order per the inbound ledger"),
    )

    flags = (
        FlagRule("below_line_minimum", "act", fn=below_line_minimum,
                 description="Ordered quantity is below this line's minimum order quantity"),
        FlagRule("not_order_multiple", "review", fn=not_order_multiple,
                 description="Ordered quantity is not a whole multiple of the order multiple"),
        FlagRule("long_lead_time", "watch", fn=long_lead_time,
                 description=f"Supplier lead time is at least {long_lead_days} days"),
        FlagRule("nothing_on_order", "watch", fn=nothing_on_order,
                 description="No units are currently on order for this line"),
        # Not derivable from the order record — declared, never fabricated:
        FlagRule("supplier_aggregate_min_not_met", "act",
                 needs="a supplier identity and aggregate minimum across stores (backend extension, map §2.5)"),
        FlagRule("lead_time_unreliable", "review",
                 needs="supplier lead-time history (not in the order record)"),
        FlagRule("price_or_terms_change", "review",
                 needs="supplier price/terms data (not in the order record)"),
    )
    return RuleSet(metrics=metrics, flags=flags, severity_order=severity_order)


# The default retail supplier/procurement ruleset.
RETAIL_SUPPLIER_RULES = build_supplier_ruleset()
