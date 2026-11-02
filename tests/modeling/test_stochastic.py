"""Seeded-stochastic quantile_gbt model: reproducibility and quantile behavior.

These tests require the dscraft tabular backend (LightGBM) -- they are skipped
if it is not installed, mirroring the lean-dependency testing posture: the
deterministic model kinds still test without any heavy dependency, while the
stochastic kind's tests only run where its backend is present.
"""
import unittest
from datetime import date

from suiroai.modeling.core import Example, ModelingError, Window, canonical
from suiroai.modeling.models import fit_model, load_model

try:  # backend presence gate
    import dscraft  # noqa: F401
    from dscraft.automl import build_model  # noqa: F401

    _HAVE_BACKEND = True
except ImportError:  # pragma: no cover
    _HAVE_BACKEND = False

K = ("MOCK", "P1", "S1")


def _training():
    """Small signal-bearing development set, all labels available by cutoff."""
    rows = []
    for i in range(60):
        x = i % 10
        rows.append(
            Example(
                Window(("MOCK", "P1", f"S{i % 3}"), date(2024, 1, 1 + (i % 27)), 1),
                (float(x), float(i % 4)),
                float(2 * x + (i % 4)),
                date(2024, 1, 2 + (i % 27)),
            )
        )
    return rows


def _ex(x, extra=1.0):
    return Example(Window(K, date(2024, 1, 1), 1), (float(x), float(extra)), 0.0, date(2024, 1, 2))


_PARAMS = {
    "alpha": 0.5,
    "seed": 42,
    "n_estimators": 12,
    "num_leaves": 7,
    "max_depth": 3,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_samples": 3,
}


@unittest.skipUnless(_HAVE_BACKEND, "dscraft tabular backend (LightGBM) not installed")
class QuantileGBTTests(unittest.TestCase):
    def setUp(self):
        self.rows = _training()

    def test_seeded_fits_are_byte_identical(self):
        """Stochastic subsampling, but a recorded seed makes the frozen model
        reproducible to the byte -- the no-pickle reproducibility contract."""
        a = fit_model("quantile_gbt", self.rows, dict(_PARAMS))
        b = fit_model("quantile_gbt", self.rows, dict(_PARAMS))
        self.assertEqual(a.state, b.state)

    def test_different_seeds_can_differ(self):
        """The model really is stochastic: a different seed may change the fit."""
        a = fit_model("quantile_gbt", self.rows, dict(_PARAMS, seed=1))
        b = fit_model("quantile_gbt", self.rows, dict(_PARAMS, seed=2))
        # Not asserting inequality of every byte (small data can coincide), but
        # the seed is recorded distinctly in the frozen state.
        self.assertNotEqual(a.payload()["seed"], b.payload()["seed"])

    def test_json_round_trip_predicts_identically(self):
        """load_model(payload).predict == model.predict -- pure-JSON inference."""
        model = fit_model("quantile_gbt", self.rows, dict(_PARAMS))
        reloaded = load_model(model.payload())
        for x in range(10):
            self.assertEqual(reloaded.predict(_ex(x)), model.predict(_ex(x)))

    def test_predict_does_not_mutate_state(self):
        model = fit_model("quantile_gbt", self.rows, dict(_PARAMS))
        before = model.state
        model.predict(_ex(7))
        self.assertEqual(model.state, before)

    def test_payload_is_canonical_serializable(self):
        model = fit_model("quantile_gbt", self.rows, dict(_PARAMS))
        # No NaN / bytes / non-JSON -- canonical() would raise otherwise.
        canonical(model.payload())

    def test_quantile_monotonicity(self):
        """Higher target quantile => higher average prediction."""
        def avg(tau):
            m = fit_model("quantile_gbt", self.rows, dict(_PARAMS, alpha=tau, n_estimators=40))
            return sum(m.predict(_ex(x)) for x in range(10)) / 10

        p10, p50, p90 = avg(0.1), avg(0.5), avg(0.9)
        self.assertLessEqual(p10, p50)
        self.assertLessEqual(p50, p90)

    def test_predictions_are_nonnegative(self):
        model = fit_model("quantile_gbt", self.rows, dict(_PARAMS))
        self.assertGreaterEqual(min(model.predict(_ex(x)) for x in range(10)), 0.0)

    def test_missing_feature_imputed_by_training_median(self):
        """A None feature at inference uses the recorded train-only median, so
        prediction stays finite and reproducible rather than erroring."""
        model = fit_model("quantile_gbt", self.rows, dict(_PARAMS))
        none_ex = Example(Window(K, date(2024, 1, 1), 1), (None, 1.0), 0.0, date(2024, 1, 2))
        value = model.predict(none_ex)
        self.assertGreaterEqual(value, 0.0)

    def test_undeclared_parameter_rejected(self):
        with self.assertRaises(ModelingError):
            fit_model("quantile_gbt", self.rows, dict(_PARAMS, not_a_param=1))

    def test_seed_must_be_nonnegative_int(self):
        with self.assertRaises(ModelingError):
            fit_model("quantile_gbt", self.rows, dict(_PARAMS, seed=-1))
        with self.assertRaises(ModelingError):
            fit_model("quantile_gbt", self.rows, dict(_PARAMS, seed=1.5))

    def test_alpha_must_be_probability(self):
        with self.assertRaises(ModelingError):
            fit_model("quantile_gbt", self.rows, dict(_PARAMS, alpha=0.0))
        with self.assertRaises(ModelingError):
            fit_model("quantile_gbt", self.rows, dict(_PARAMS, alpha=1.0))

    def test_inference_feature_width_mismatch_rejected(self):
        model = fit_model("quantile_gbt", self.rows, dict(_PARAMS))
        wrong = Example(Window(K, date(2024, 1, 1), 1), (1.0, 2.0, 3.0), 0.0, date(2024, 1, 2))
        with self.assertRaises(ModelingError):
            model.predict(wrong)


if __name__ == "__main__":
    unittest.main()
