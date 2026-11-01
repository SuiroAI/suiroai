"""A-PR4 (DSC-73): generic rule engine + the retail restocking ruleset.

Two layers are tested:
1. The engine (``service/derive.py``) is domain-neutral — with EMPTY_RULES it computes nothing;
   it evaluates whatever metrics/flags a supplied RuleSet declares; metric None = "not enough data"
   and non-derivable flags surface as unavailable, never fabricated.
2. The retail **restocking** ruleset (one retail problem type) computes cover and stock-out risk
   from the authoritative backend order record, with overridable thresholds (nothing baked in),
   and declares the flags it cannot yet derive as unavailable with what they need.
"""
from __future__ import annotations

import unittest

from suiroai.service.derive import derive, evaluate_flags, evaluate_metrics
from suiroai.service.rules import EMPTY_RULES, FlagRule, MetricRule, RuleSet
from suiroai.service.retail import RETAIL_CHAIN, RETAIL_PROBLEMS, ruleset_for
from suiroai.service.retail.restocking import build_restocking_ruleset
from suiroai.service.retail.suppliers import build_supplier_ruleset


class GenericEngineTests(unittest.TestCase):
    def test_empty_ruleset_computes_nothing(self):
        out = derive({"anything": 1}, EMPTY_RULES)
        self.assertEqual(out["metrics"], {})
        self.assertEqual(out["flags"]["active"], [])
        self.assertEqual(out["flags"]["unavailable"], [])

    def test_engine_evaluates_supplied_metrics_and_flags(self):
        # A toy, non-retail ruleset proves the engine carries no domain knowledge.
        rs = RuleSet(
            metrics=(MetricRule("double", lambda r, m: r["x"] * 2),
                     MetricRule("plus_prev", lambda r, m: m["double"] + 1)),
            flags=(FlagRule("big", "high", fn=lambda r, m: m["double"] >= 10),
                   FlagRule("needs_more", "low", needs="a y field")),
            severity_order=("high", "low"),
        )
        out = derive({"x": 6}, rs)
        self.assertEqual(out["metrics"], {"double": 12, "plus_prev": 13})
        self.assertEqual(out["flags"]["active"], [{"code": "big", "severity": "high"}])
        self.assertEqual(out["flags"]["unavailable"], [{"code": "needs_more", "needs": "a y field"}])

    def test_metric_none_on_missing_data_not_crash(self):
        rs = RuleSet(metrics=(MetricRule("ratio", lambda r, m: r["a"] / r["b"]),))
        # Division by zero / missing key → None ("not enough data"), never a raise or guess.
        self.assertIsNone(evaluate_metrics({"a": 1, "b": 0}, rs)["ratio"])
        self.assertIsNone(evaluate_metrics({}, rs)["ratio"])

    def test_active_flags_sorted_by_declared_severity(self):
        rs = RuleSet(
            flags=(FlagRule("w", "watch", fn=lambda r, m: True),
                   FlagRule("a", "act", fn=lambda r, m: True)),
            severity_order=("act", "review", "watch"),
        )
        order = [f["code"] for f in evaluate_flags({}, rs, {})["active"]]
        self.assertEqual(order, ["a", "w"])   # act before watch


# A backend order row like the ones in the fixtures.
_ORDER = {
    "usable_on_hand_quantity": 5,
    "forecast_quantity": 20,
    "forecast_horizon_start": "2025-12-01",
    "forecast_horizon_end": "2025-12-14",
    "eligible_receipt_quantity": 5,
}


class RetailRestockingRulesTests(unittest.TestCase):
    def test_registry_exposes_restocking_and_suppliers(self):
        self.assertIn("restocking", RETAIL_PROBLEMS)
        self.assertIn("suppliers", RETAIL_PROBLEMS)   # suppliers are part of the retail chain
        self.assertIs(ruleset_for("restocking"), RETAIL_PROBLEMS["restocking"])

    def test_chain_map_covers_end_to_end_with_built_areas(self):
        stages = {c["stage"]: c["status"] for c in RETAIL_CHAIN}
        # restocking and suppliers are built; the rest of the chain is declared as planned.
        self.assertEqual(stages["restocking"], "built")
        self.assertEqual(stages["suppliers"], "built")
        self.assertIn("pricing_markdown", stages)
        self.assertIn("fulfilment", stages)

    def test_unknown_problem_area_raises_not_falls_back(self):
        with self.assertRaises(KeyError):
            ruleset_for("pricing")   # not built yet; must not silently use another area

    def test_cover_computed_from_forecast(self):
        rs = ruleset_for("restocking")
        metrics = evaluate_metrics(_ORDER, rs)
        # 20 units over 14 days = 1.4286/day; 5 on hand / 1.4286 = 3.5 days = 0.5 weeks.
        self.assertAlmostEqual(metrics["cover"], 0.5, places=2)
        self.assertEqual(metrics["target_cover"], 2.5)

    def test_cover_none_when_no_forecast(self):
        rs = ruleset_for("restocking")
        self.assertIsNone(evaluate_metrics({**_ORDER, "forecast_quantity": 0}, rs)["cover"])

    def test_stock_out_risk_true_when_low_cover_and_no_incoming(self):
        rs = ruleset_for("restocking")
        order = {**_ORDER, "eligible_receipt_quantity": 0}   # cover 0.5 < 1, nothing incoming
        active = [f["code"] for f in derive(order, rs)["flags"]["active"]]
        self.assertIn("stock_out_risk", active)

    def test_stock_out_risk_false_when_incoming(self):
        rs = ruleset_for("restocking")
        active = [f["code"] for f in derive(_ORDER, rs)["flags"]["active"]]   # 5 incoming
        self.assertNotIn("stock_out_risk", active)

    def test_non_derivable_flags_reported_unavailable_not_fabricated(self):
        rs = ruleset_for("restocking")
        unavailable = {f["code"] for f in derive(_ORDER, rs)["flags"]["unavailable"]}
        self.assertIn("supplier_min_not_met", unavailable)
        self.assertIn("expiry_risk", unavailable)
        # every unavailable flag states what it needs
        for f in derive(_ORDER, rs)["flags"]["unavailable"]:
            self.assertTrue(f["needs"])

    def test_thresholds_are_overridable_not_baked_in(self):
        # Raise the stock-out threshold so the same order now trips the flag even with incoming.
        rs = build_restocking_ruleset(stock_out_threshold=1.0)
        strict = build_restocking_ruleset(stock_out_threshold=5.0, target_cover=4.0)
        self.assertEqual(evaluate_metrics(_ORDER, strict)["target_cover"], 4.0)
        # With a very high threshold the low-cover line is at risk only if nothing incoming;
        # incoming here (5) still suppresses it, proving the predicate uses config not constants.
        order_no_incoming = {**_ORDER, "eligible_receipt_quantity": 0}
        active = [f["code"] for f in derive(order_no_incoming, strict)["flags"]["active"]]
        self.assertIn("stock_out_risk", active)


# A backend order row with supplier/procurement fields.
_SUPPLIER_ORDER = {
    "supplier_lead_calendar_days": 7,
    "review_period_calendar_days": 7,
    "on_order_summary_quantity": 5,
    "order_multiple": 5,
    "minimum_positive_order_quantity": 5,
    "approved_order_quantity": 15,
    "eligible_receipt_quantity": 5,
}


class RetailSupplierRulesTests(unittest.TestCase):
    def test_supplier_metrics_derived(self):
        rs = ruleset_for("suppliers")
        m = evaluate_metrics(_SUPPLIER_ORDER, rs)
        self.assertEqual(m["lead_time_days"], 7)
        self.assertEqual(m["lead_plus_review_days"], 14)
        self.assertEqual(m["on_order_quantity"], 5)

    def test_below_line_minimum_flag(self):
        rs = ruleset_for("suppliers")
        order = {**_SUPPLIER_ORDER, "approved_order_quantity": 3}   # below minimum of 5
        active = [f["code"] for f in derive(order, rs)["flags"]["active"]]
        self.assertIn("below_line_minimum", active)

    def test_not_order_multiple_flag(self):
        rs = ruleset_for("suppliers")
        order = {**_SUPPLIER_ORDER, "approved_order_quantity": 12}   # not a multiple of 5
        active = [f["code"] for f in derive(order, rs)["flags"]["active"]]
        self.assertIn("not_order_multiple", active)

    def test_long_lead_time_overridable(self):
        order = {**_SUPPLIER_ORDER, "supplier_lead_calendar_days": 10}
        default = build_supplier_ruleset()                       # threshold 14 → not flagged
        strict = build_supplier_ruleset(long_lead_days=7)        # threshold 7 → flagged
        self.assertNotIn("long_lead_time",
                         [f["code"] for f in derive(order, default)["flags"]["active"]])
        self.assertIn("long_lead_time",
                      [f["code"] for f in derive(order, strict)["flags"]["active"]])

    def test_aggregate_supplier_minimum_declared_unavailable(self):
        rs = ruleset_for("suppliers")
        unavailable = {f["code"] for f in derive(_SUPPLIER_ORDER, rs)["flags"]["unavailable"]}
        self.assertIn("supplier_aggregate_min_not_met", unavailable)


if __name__ == "__main__":
    unittest.main()
