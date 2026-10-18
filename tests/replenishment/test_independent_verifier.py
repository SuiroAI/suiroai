"""MOCK producer-to-DSC-30 integration; no real execution/approval is claimed."""
import csv
import io
import json
import unittest

from suiroai.verification.arithmetic import reconcile_orders
from test_handoff import KEY, calculate, scenario


def independent_check(handoff, scope, candidate):
    refs = {r["artifact_id"]: r for r in handoff.external_refs}

    def operational(name):
        rows = list(csv.DictReader(io.StringIO(handoff.read(refs[name]).decode())))
        return [dict(row, source_namespace=KEY[0]) for row in rows]

    return reconcile_orders(candidate["orders"], candidate["exceptions"],
        scope_keys=json.loads(handoff.read(scope)),
        forecast_rows=json.loads(handoff.read(refs["mock-november-30-forecast"])),
        inventory_rows=operational("mock-stock"),
        receipt_rows=operational("mock-receipts"),
        policy_rows=operational("mock-policy"), name_rows=[],
        ledger_complete=True, receipt_timing="unknown", require_product_names=False)


class IndependentVerifierIntegration(unittest.TestCase):
    def test_independent_verifier_agrees_with_candidate_from_bound_mock_bytes(self):
        h, scope, _ = scenario()
        candidate = calculate(h, scope)
        checked = independent_check(h, scope, candidate)
        self.assertTrue(checked["checks"])
        self.assertTrue(all(c["status"] == "pass" for c in checked["checks"]))
        self.assertEqual(checked["expected_orders"][0]["rounded_order_quantity"], "5")
        self.assertEqual(checked["exceptions"], [])

    def test_independent_verifier_accepts_evidenced_withholding_for_late_receipt(self):
        def late(args):
            args[1][0][KEY][0][1].update(Usable_On_Hand_Qty="3", On_Order_Qty="8")
            args[1][2][KEY][0][1]["Safety_Stock_Qty"] = "0"
            args[1][1][KEY][0][1].update(Expected_Arrival_Date="2025-12-04", Incoming_Qty="8")
            for (_, row), value in zip(args[1][3][KEY], (2, 4, 1, 1)):
                row["quantity"] = value
        h, scope, _ = scenario(mutate_inputs=late)
        candidate = calculate(h, scope)
        checked = independent_check(h, scope, candidate)
        self.assertEqual(candidate["orders"], [])
        self.assertTrue(all(c["status"] == "pass" for c in checked["checks"]))
        self.assertEqual(len(checked["exceptions"]), 1)
        self.assertEqual(checked["expected_orders"], [])
