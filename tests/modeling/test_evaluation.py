"""Explicit synthetic contract fixtures, not real retail evaluation acceptance."""
from dataclasses import replace
from datetime import date, timedelta
import unittest
from unittest.mock import patch

from suiroai.modeling.core import CUTOFF, Example, ModelingError, Window
from suiroai.modeling.evaluation import CandidateSpec, RollingFold, compare_candidates, evaluate_initial
from suiroai.modeling.models import fit_model


KEY = ("mock-task", "mock-product", "mock-store")


def example(origin, feature, actual, *, key=KEY, horizon=1, available_on=None):
    return Example(Window(key, origin, horizon), (feature,), actual, available_on)


def folds():
    origin = date(2025, 10, 1)
    train = tuple(example(origin - timedelta(days=10-i), float(i), float(2*i+2)) for i in range(5))
    valid = (example(origin, 5.0, 12.0),)
    return (RollingFold("mock-fold", train, valid),)


def spec(name="initial", kind="ridge", features="original"):
    return CandidateSpec(name, kind, features, {"alpha": 0.01} if kind == "ridge" else {},
                         "Synthetic fixture testing a bounded candidate.")


class EvaluationTests(unittest.TestCase):
    def test_initial_comparison_is_measured_and_parent_unverified(self):
        result = evaluate_initial(folds(), spec("baseline", "past_mean"), spec(),
                                  population_id="mock-population")
        self.assertEqual(result["comparison"], "better")
        self.assertFalse(result["parent_verified"])
        self.assertFalse(result["requires_parent_review"])
        self.assertEqual(result["baseline"]["scores"][0]["value"], 6.0)
        self.assertLess(result["initial"]["scores"][0]["value"], 0.1)
        self.assertIn("not the customer's actual process", result["baseline_label"])
        self.assertEqual(result["fit_count"], 2)
        self.assertEqual(result["baseline"]["predictions"][0]["origin"], "2025-10-01")

    def test_equal_or_worse_requires_parent_review(self):
        result = evaluate_initial(folds(), spec("baseline", "past_mean"), spec("initial", "mean"),
                                  population_id="mock-population")
        self.assertEqual(result["comparison"], "equal")
        self.assertTrue(result["requires_parent_review"])

    def test_fit_sees_only_training_and_preprocessing_stays_fold_local(self):
        calls = []
        def spy(kind, training, parameters):
            calls.append(tuple(training))
            return fit_model(kind, training, parameters)
        fold = folds()[0]
        with patch("suiroai.modeling.evaluation.fit_model", side_effect=spy):
            result = evaluate_initial((fold,), spec("baseline", "past_mean"), spec(),
                                      population_id="mock-population")
        self.assertEqual(calls, [fold.training, fold.training])
        fitted = result["initial"]["fitted_folds"][0]["model"]
        self.assertEqual(fitted["medians"], [2.0])
        self.assertEqual(fitted["centers"], [2.0])
        self.assertEqual(fitted["training_count"], 5)

    def test_training_label_availability_and_full_horizon_are_enforced(self):
        fold = folds()[0]
        future = replace(fold.training[0], available_on=date(2025, 10, 2))
        with self.assertRaisesRegex(ModelingError, "training labels"):
            evaluate_initial((replace(fold, training=(future,)),), spec("baseline", "past_mean"),
                             spec(), population_id="mock")
        late = example(CUTOFF, 1.0, 4)
        with self.assertRaisesRegex(ModelingError, "November 30"):
            evaluate_initial((replace(fold, validation=(late,)),), spec("baseline", "past_mean"),
                             spec(), population_id="mock")

    def test_validation_and_training_obey_declared_year_partitions(self):
        f = folds()[0]
        bad_validation = example(date(2024, 12, 30), 1.0, 2)
        with self.assertRaisesRegex(ModelingError, "2025 development"):
            evaluate_initial((replace(f, validation=(bad_validation,)),), spec("baseline", "past_mean"),
                             spec(), population_id="mock")
        old_training = example(date(2021, 12, 30), 1.0, 2)
        with self.assertRaisesRegex(ModelingError, "2022 history"):
            evaluate_initial((replace(f, training=(old_training,)),), spec("baseline", "past_mean"),
                             spec(), population_id="mock")

    def test_comparison_requires_past_eligibility_even_without_baseline(self):
        f = folds()[0]
        new_horizon = replace(f.validation[0], window=Window(KEY, date(2025, 10, 1), 2))
        with patch("suiroai.modeling.evaluation.fit_model") as fitter:
            with self.assertRaisesRegex(ModelingError, "key/horizon.*training"):
                compare_candidates({"original": (replace(f, validation=(new_horizon,)),)},
                                   [spec("global-mean", "mean")], population_id="mock")
            fitter.assert_not_called()

    def test_training_cutoff_cannot_follow_origin(self):
        fold = replace(folds()[0], training_end=date(2025, 10, 2))
        with self.assertRaisesRegex(ModelingError, "cutoff"):
            evaluate_initial((fold,), spec("baseline", "past_mean"), spec(), population_id="mock")

    def test_no_automatic_zero_or_unseen_series_baseline(self):
        fold = folds()[0]
        other_key = ("mock-task", "unseen-product", "mock-store")
        fold = replace(fold, validation=(replace(fold.validation[0], window=Window(other_key, date(2025, 10, 1), 1)),))
        with self.assertRaisesRegex(ModelingError, "past-only training"):
            evaluate_initial((fold,), spec("baseline", "past_mean"), spec(), population_id="mock")

    def test_comparison_preserves_original_and_evaluates_augmented(self):
        original = folds()
        augmented = tuple(replace(f, training=tuple(replace(e, features=(e.features[0], 9.0)) for e in f.training),
                                  validation=tuple(replace(e, features=(e.features[0], 9.0)) for e in f.validation))
                          for f in original)
        result = compare_candidates({"original": original, "augmented": augmented},
                                    [spec("reference", "mean"), spec("augmented-ridge", "ridge", "augmented")],
                                    population_id="mock-population")
        self.assertEqual(result["selected_candidate_id"], "augmented-ridge")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["fit_count"], 2)
        self.assertFalse(result["parent_verified"])
        self.assertEqual(result["candidates"][0]["predictions"][0]["actual"],
                         result["candidates"][1]["predictions"][0]["actual"])

    def test_equal_populations_means_origins_horizons_labels_and_folds(self):
        first = folds()
        fold = first[0]
        changes = [replace(fold, validation=(replace(fold.validation[0], actual=999),)),
                   replace(fold, validation=(replace(fold.validation[0], window=Window(KEY, date(2025, 10, 2), 1)),)),
                   replace(fold, validation=(replace(fold.validation[0], window=Window(KEY, date(2025, 10, 1), 2)),)),
                   replace(fold, fold_id="different")]
        for changed in changes:
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ModelingError, "equal populations|past-only training"):
                    compare_candidates({"original": first, "augmented": (changed,)},
                                       [spec("reference", "mean"), spec("augmented", "ridge", "augmented")],
                                       population_id="mock")

    def test_limits_reject_before_any_fit(self):
        with patch("suiroai.modeling.evaluation.fit_model") as fitter:
            with self.assertRaisesRegex(ModelingError, "fit budget"):
                evaluate_initial(folds(), spec("baseline", "past_mean"), spec(),
                                 population_id="mock", max_fits=1)
            with self.assertRaisesRegex(ModelingError, "candidate budget"):
                compare_candidates({"original": folds()}, [spec("a"), spec("b")],
                                   population_id="mock", max_candidates=1)
            fitter.assert_not_called()

    def test_timeout_is_execution_error_not_measured_failure(self):
        with patch("suiroai.modeling.evaluation.monotonic", side_effect=[0.0, 2.0]):
            with self.assertRaisesRegex(ModelingError, "runtime budget"):
                evaluate_initial(folds(), spec("baseline", "past_mean"), spec(),
                                 population_id="mock", max_seconds=1)

    def test_tie_keeps_predeclared_reference(self):
        result = compare_candidates({"original": folds()}, [spec("original", "mean"), spec("other", "mean")],
                                    population_id="mock")
        self.assertEqual(result["selected_candidate_id"], "original")

    def test_duplicate_validation_window_rejected(self):
        f = folds()[0]
        with self.assertRaisesRegex(ModelingError, "duplicate development"):
            compare_candidates({"original": (f, replace(f, fold_id="another"))}, [spec()], population_id="mock")


if __name__ == "__main__":
    unittest.main()
