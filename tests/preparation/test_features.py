"""MOCK initial feature safety checks, not model or customer acceptance.

Check initial calendar and identifier features, fold-fitted vocabularies,
daily grain, and target availability with explicit synthetic inputs.
"""
from copy import deepcopy
import unittest

from mock_data import packet, sale
from suiroai.preparation.worker import PreparationError, prepare_development
from suiroai.preparation.features import (build_features, fit_categories, horizon_target,
                                         transform_categories, validate_feature_rows)


class MockFeatureTests(unittest.TestCase):
    def setUp(self):
        args, _ = packet([sale(1, Order_Date="2024-12-01"), sale(2, Order_Date="2024-12-30"),
                          sale(3, Order_Date="2025-01-02")])
        self.daily = prepare_development(**args)["daily"]
        self.features = build_features(self.daily, source_namespace="mock-retail")

    def test_calendar_only_inputs_and_separate_forecast_origin(self):
        self.assertEqual(self.features["origin_rows"], [{"source_namespace": "mock-retail", "Product_ID": "MOCK-P1", "Store_ID": "MOCK-S1", "origin": "2025-11-30"}])
        self.assertTrue(self.features["no_fitted_transformations"])
        self.assertEqual(self.features["rows"][0]["origin"], "2024-12-29")
        self.assertEqual(self.features["rows"][0]["target_weekday"], 0)
        self.assertNotIn("target_quantity", self.features["rows"][0])

    def test_new_key_does_not_create_forecast_population_on_its_first_observed_day(self):
        first = deepcopy(self.daily[0])
        first.update(Product_ID="MOCK-NEW-P", Order_Date="2025-01-03")
        later = deepcopy(first)
        later["Order_Date"] = "2025-01-05"
        result = build_features([later, *self.daily, first], source_namespace="mock-retail")
        new_rows = [r for r in result["rows"] if r["Product_ID"] == "MOCK-NEW-P"]
        self.assertEqual([r["target_date"] for r in new_rows], ["2025-01-05"])
        self.assertEqual(result["excluded_unseen_key_target_rows"], 2)
        self.assertIn("MOCK-NEW-P", [r["Product_ID"] for r in result["origin_rows"]])

    def test_future_realized_or_operational_predictors_rejected(self):
        for field in ("Quantity", "Revenue", "Order_Status", "Return_Flag", "Inventory_Level", "Delivery_Days", "Usable_On_Hand_Qty", "target_quantity", "observed_record_day"):
            rows = deepcopy(self.features["rows"])
            rows[0][field] = "future"
            with self.subTest(field=field), self.assertRaisesRegex(PreparationError, "leakage"):
                validate_feature_rows(rows)

    def test_wrong_daily_and_feature_grain_detected(self):
        with self.assertRaisesRegex(PreparationError, "wrong grain"):
            build_features(self.daily + [deepcopy(self.daily[0])], source_namespace="mock-retail")
        with self.assertRaisesRegex(PreparationError, "wrong feature grain"):
            validate_feature_rows(self.features["rows"] + [deepcopy(self.features["rows"][0])])

    def test_future_dates_or_origin_and_calendar_tampering_detected(self):
        for field, value in (("target_date", "2025-12-01"), ("origin", "2025-01-02"), ("target_month", 9)):
            rows = deepcopy(self.features["rows"])
            rows[1][field] = value
            with self.subTest(field=field), self.assertRaises(PreparationError):
                validate_feature_rows(rows)

    def test_fold_vocabulary_does_not_fit_validation_or_unknown_keys(self):
        rows = self.features["rows"]
        fit = fit_categories(rows[:1], training_end="2024-12-31", validation_start="2025-01-01")
        changed = deepcopy(rows[1:])
        changed[0]["Product_ID"], changed[0]["Store_ID"] = "MOCK-FUTURE-P", "MOCK-FUTURE-S"
        transformed = transform_categories(changed, fit)
        self.assertEqual((transformed[0]["product_code"], transformed[0]["store_code"]), (-1, -1))
        self.assertEqual(fit.products, ("MOCK-P1",))
        with self.assertRaisesRegex(PreparationError, "validation/future"):
            fit_categories(rows, training_end="2024-12-31", validation_start="2025-01-01")

    def test_no_horizon_target_from_global_coverage_or_incomplete_observations(self):
        kwargs = dict(product_id="MOCK-P1", store_id="MOCK-S1", origin="2024-11-30", horizon_days=1)
        self.assertIsNone(horizon_target(self.daily, **kwargs))
        supported = deepcopy(self.daily)
        supported[0].update(complete_daily_sales=True, completeness_evidence_refs=[{"mock": "explicit per-series evidence"}])
        self.assertEqual(horizon_target(supported, **kwargs), 3)
        self.assertIsNone(horizon_target(supported, **dict(kwargs, horizon_days=2)))
        supported[0].pop("completeness_evidence_refs")
        self.assertIsNone(horizon_target(supported, **kwargs))
        self.assertIsNone(horizon_target(supported, product_id="MOCK-P1", store_id="MOCK-S1", origin="2025-11-30", horizon_days=1))


if __name__ == "__main__":
    unittest.main()
