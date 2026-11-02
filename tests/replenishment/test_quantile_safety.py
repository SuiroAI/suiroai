"""Distribution-aware (service-level quantile) safety stock in DSC-29 arithmetic.

Expected numbers are computed by hand from the displayed inputs, never from the
producer under test. These verify the ADDITIVE quantile-safety path: when the
frozen forecast supplies a per-day service-level upper quantile, the horizon gap
between that quantile and the point forecast becomes the safety buffer, floored
by the declared policy Safety_Stock_Qty (the quantile path can only raise safety,
never lower it). The independent verifier must recompute the same effective
safety from the same forecast bytes.
"""
import csv
import io
import json
import unittest

from test_calculation import KEY, inputs
from test_handoff import KEY as HKEY
from test_handoff import calculate, scenario

from suiroai.replenishment.calculation import _calculate_key
from suiroai.replenishment.context import InputError
from suiroai.verification.arithmetic import reconcile_orders


def _with_v1_marginal(args, quantiles, level="0.95"):
    """Attach a LEGACY v1 per-day marginal service-level quantile (fail-closed path)."""
    rows = args[1][3][KEY]
    for (_, row), q in zip(rows, quantiles):
        row["service_level_quantity"] = str(q)
        row["service_level"] = level


def _with_v2_cdf(args, cdfs, level="0.95", dependence="independent"):
    """Attach a frozen_forecast/v2 per-day demand CDF trajectory.

    ``cdfs`` is one ``(support, cumulative)`` pair per day; ``support`` are integer
    demand levels, ``cumulative`` the non-decreasing CDF ending at 1.0.
    """
    rows = args[1][3][KEY]
    for (_, row), (support, cumulative) in zip(rows, cdfs):
        row["schema_version"] = "frozen_forecast/v2"
        row["demand_support"] = [int(s) for s in support]
        row["demand_cumulative"] = [str(c) for c in cumulative]
        row["service_level"] = level
        row["dependence_model"] = dependence


def _brute_joint_quantile(cdfs, level):
    """Independent hand-oracle: exact joint quantile by brute-force convolution.

    Deliberately NOT the production helper -- a separate implementation so the test
    checks the producer, not itself.
    """
    from fractions import Fraction as F
    joint = {0: F(1)}
    for support, cumulative in cdfs:
        pmf, prev = {}, F(0)
        for v, c in zip(support, cumulative):
            pmf[v] = F(str(c)) - prev
            prev = F(str(c))
        nxt = {}
        for a, pa in joint.items():
            for b, pb in pmf.items():
                nxt[a + b] = nxt.get(a + b, F(0)) + pa * pb
        joint = nxt
    acc = F(0)
    for total in sorted(joint):
        acc += joint[total]
        if acc >= F(str(level)):
            return total
    return max(joint)


class QuantileSafetyArithmetic(unittest.TestCase):
    def test_joint_horizon_quantile_raises_safety_above_policy(self):
        # 4 days, each demand 1 w.p. 0.9 else 5 (point=1). usable 4, policy safety 2.
        # point_total = 1+1+1+1 = 4. The JOINT 95th pct is computed by an independent
        # brute-force oracle below -- NOT by summing per-day 95th percentiles (each
        # day's own 95th pct is 5, whose naive sum 20 would be wrong).
        cdfs = [([1, 5], ["0.9", "1.0"])] * 4
        expected_joint = _brute_joint_quantile(cdfs, "0.95")   # exact horizon quantity
        expected_gap = max(0, expected_joint - 4)              # over point_total 4
        args = list(inputs(demands=(1, 1, 1, 1), usable=4, safety=2, minimum=1, multiple=1))
        _with_v2_cdf(args, cdfs, level="0.95")
        row, audit = _calculate_key(*args)
        self.assertEqual(audit["quantile_safety_stock_exact"], str(expected_gap))
        self.assertEqual(audit["effective_safety_stock_exact"], str(max(2, expected_gap)))
        self.assertEqual(audit["safety_stock_basis"], "service_level_quantile")
        self.assertEqual(audit["policy_safety_stock_quantity"], 2)
        # Need = point_total(4) + effective_safety - usable(4) - eligible(0).
        self.assertEqual(row["raw_order_need"], max(0, 4 + max(2, expected_gap) - 4))

    def test_policy_floor_applies_when_joint_gap_is_smaller(self):
        # A near-deterministic CDF: joint 95th pct barely exceeds point_total, so the
        # policy floor (3) dominates the small distribution-aware buffer.
        cdfs = [([1, 2], ["0.99", "1.0"])] * 4   # point 1 per day, point_total 4
        expected_joint = _brute_joint_quantile(cdfs, "0.95")
        expected_gap = max(0, expected_joint - 4)
        self.assertLess(expected_gap, 3)  # precondition: gap below the policy floor
        args = list(inputs(demands=(1, 1, 1, 1), usable=4, safety=3, minimum=1, multiple=1))
        _with_v2_cdf(args, cdfs, level="0.95")
        row, audit = _calculate_key(*args)
        self.assertEqual(audit["quantile_safety_stock_exact"], str(expected_gap))
        self.assertEqual(audit["effective_safety_stock_exact"], "3")
        self.assertEqual(audit["safety_stock_basis"], "policy_floor")
        self.assertEqual(row["raw_order_need"], 4 + 3 - 4)

    def test_absent_service_level_keeps_pure_policy_path(self):
        args = list(inputs(demands=(1, 1, 4, 4), usable=4, safety=2))
        row, audit = _calculate_key(*args)
        self.assertIsNone(audit["quantile_safety_stock_exact"])
        self.assertEqual(audit["safety_stock_basis"], "policy")
        self.assertEqual(row["raw_order_need"], 8)  # 10 + 2 - 4

    def test_v1_marginal_service_level_is_withheld_fail_closed(self):
        # A legacy v1 per-day marginal quantile cannot drive horizon safety: it must
        # WITHHOLD (fail closed), not silently sum per-day marginals.
        args = list(inputs(demands=(1, 1, 4, 4), usable=4, safety=2))
        _with_v1_marginal(args, quantiles=(2, 2, 6, 6))
        with self.assertRaises(InputError):
            _calculate_key(*args)

    def test_comonotonic_dependence_is_rejected(self):
        cdfs = [([1, 5], ["0.9", "1.0"])] * 4
        args = list(inputs(demands=(1, 1, 1, 1), usable=4, safety=2))
        _with_v2_cdf(args, cdfs, level="0.95", dependence="comonotonic")
        with self.assertRaises(InputError):
            _calculate_key(*args)

    def test_partial_v2_trajectory_rejected(self):
        args = list(inputs(demands=(1, 1, 4, 4), usable=4, safety=2))
        # Only the first two days carry a CDF -> incomplete over horizon.
        rows = args[1][3][KEY]
        for (_, row), (support, cumulative) in zip(rows[:2], [([1, 5], ["0.9", "1.0"])] * 2):
            row["schema_version"] = "frozen_forecast/v2"
            row["demand_support"] = support
            row["demand_cumulative"] = cumulative
            row["service_level"] = "0.95"
            row["dependence_model"] = "independent"
        with self.assertRaises(InputError):
            _calculate_key(*args)


class QuantileSafetyEndToEnd(unittest.TestCase):
    def test_independent_verifier_agrees_with_joint_safety_candidate(self):
        """Producer and DSC-30 verifier must derive the SAME effective safety from the
        same v2 CDF forecast bytes -- both via the joint method, not a marginal sum."""
        def add_cdf(args):
            rows = args[1][3][HKEY]
            # Each day: demand = point w.p. 0.9 else point+4. v2 CDF, independent.
            for _, row in rows:
                point = int(float(row["quantity"]))
                row["schema_version"] = "frozen_forecast/v2"
                row["demand_support"] = [point, point + 4]
                row["demand_cumulative"] = ["0.9", "1.0"]
                row["service_level"] = "0.95"
                row["dependence_model"] = "independent"

        h, scope, _ = scenario(mutate_inputs=add_cdf)
        candidate = calculate(h, scope)
        self.assertEqual(candidate["exceptions"], [])
        order = candidate["orders"][0]

        refs = {r["artifact_id"]: r for r in h.external_refs}

        def operational(name):
            reader = csv.DictReader(io.StringIO(h.read(refs[name]).decode()))
            return [dict(row, source_namespace=HKEY[0]) for row in reader]

        checked = reconcile_orders(
            candidate["orders"], candidate["exceptions"],
            scope_keys=json.loads(h.read(scope)),
            forecast_rows=json.loads(h.read(refs["mock-november-30-forecast"])),
            inventory_rows=operational("mock-stock"),
            receipt_rows=operational("mock-receipts"),
            policy_rows=operational("mock-policy"), name_rows=[],
            ledger_complete=True, receipt_timing="unknown", require_product_names=False)
        self.assertTrue(checked["checks"])
        self.assertTrue(all(c["status"] == "pass" for c in checked["checks"]))
        self.assertEqual(checked["exceptions"], [])
        # Verifier's independently recomputed order equals the producer's.
        self.assertEqual(checked["expected_orders"][0]["rounded_order_quantity"],
                         str(order["rounded_order_quantity"]))


if __name__ == "__main__":
    unittest.main()
