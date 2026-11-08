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


def _with_service_level(args, quantiles, level="0.95"):
    """Attach a service-level upper quantile to each daily forecast row."""
    forecast_index = args[1][3]
    rows = forecast_index[KEY]
    for (_, row), q in zip(rows, quantiles):
        row["service_level_quantity"] = str(q)
        row["service_level"] = level


class QuantileSafetyArithmetic(unittest.TestCase):
    def test_quantile_gap_raises_safety_above_policy(self):
        # Point demands sum: 1+1+4+4 = 10; usable 4; policy safety 2.
        # Service-level quantiles sum: 2+2+6+6 = 16; gap = 16-10 = 6 > policy 2.
        # Effective safety = max(2, 6) = 6. Need = 10 + 6 - 4 - 0 = 12.
        args = list(inputs(demands=(1, 1, 4, 4), usable=4, safety=2, minimum=1, multiple=1))
        _with_service_level(args, quantiles=(2, 2, 6, 6))
        row, audit = _calculate_key(*args)
        self.assertEqual(audit["quantile_safety_stock_exact"], "6")
        self.assertEqual(audit["effective_safety_stock_exact"], "6")
        self.assertEqual(audit["safety_stock_basis"], "service_level_quantile")
        self.assertEqual(row["raw_order_need"], 12)
        self.assertEqual(row["rounded_order_quantity"], 12)
        # The schema-validated row reports the safety ACTUALLY APPLIED (effective),
        # preserving the contract invariant raw_need == forecast+safety-usable-eligible.
        self.assertEqual(row["safety_stock_quantity"], 6)
        self.assertEqual(audit["policy_safety_stock_quantity"], 2)

    def test_policy_floor_applies_when_quantile_gap_is_smaller(self):
        # Quantile gap = (2+1+4+4) - (1+1+4+4) = 1 < policy 3 -> policy floors it.
        args = list(inputs(demands=(1, 1, 4, 4), usable=4, safety=3, minimum=1, multiple=1))
        _with_service_level(args, quantiles=(2, 1, 4, 4))
        row, audit = _calculate_key(*args)
        self.assertEqual(audit["quantile_safety_stock_exact"], "1")
        self.assertEqual(audit["effective_safety_stock_exact"], "3")
        self.assertEqual(audit["safety_stock_basis"], "policy_floor")
        # Need = 10 + 3 - 4 - 0 = 9.
        self.assertEqual(row["raw_order_need"], 9)

    def test_absent_service_level_keeps_pure_policy_path(self):
        args = list(inputs(demands=(1, 1, 4, 4), usable=4, safety=2))
        row, audit = _calculate_key(*args)
        self.assertIsNone(audit["quantile_safety_stock_exact"])
        self.assertEqual(audit["safety_stock_basis"], "policy")
        self.assertEqual(row["raw_order_need"], 8)  # 10 + 2 - 4

    def test_quantile_below_point_forecast_is_rejected(self):
        args = list(inputs(demands=(1, 1, 4, 4), usable=4, safety=2))
        _with_service_level(args, quantiles=(0, 1, 4, 4))  # 0 < point 1 on day 1
        with self.assertRaises(InputError):
            _calculate_key(*args)

    def test_service_level_must_exceed_median(self):
        args = list(inputs(demands=(1, 1, 4, 4), usable=4, safety=2))
        _with_service_level(args, quantiles=(2, 2, 6, 6), level="0.5")  # not > 0.5
        with self.assertRaises(InputError):
            _calculate_key(*args)

    def test_partial_service_level_trajectory_rejected(self):
        args = list(inputs(demands=(1, 1, 4, 4), usable=4, safety=2))
        # Only the first two days carry a quantile -> incomplete over horizon.
        rows = args[1][3][KEY]
        for (_, row), q in zip(rows[:2], (2, 2)):
            row["service_level_quantity"] = str(q)
            row["service_level"] = "0.95"
        with self.assertRaises(InputError):
            _calculate_key(*args)


class QuantileSafetyEndToEnd(unittest.TestCase):
    def test_independent_verifier_agrees_with_quantile_safety_candidate(self):
        """Producer and DSC-30 verifier must derive the SAME effective safety
        from the same service-level forecast bytes."""
        def add_quantiles(args):
            rows = args[1][3][HKEY]
            # Default fixture demands; give each day a +1 service-level buffer.
            for _, row in rows:
                point = int(float(row["quantity"]))
                row["service_level_quantity"] = str(point + 1)
                row["service_level"] = "0.9"

        h, scope, _ = scenario(mutate_inputs=add_quantiles)
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
