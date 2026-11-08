"""Seeded stochastic gradient-boosted quantile forecasting via dscraft.

This module adds a genuinely *stochastic* model family to DSC-28 -- gradient
boosted trees fitted with row/feature subsampling -- while preserving every
determinism and no-pickle guarantee the rest of the modeling package relies
on. The trick is a clean split of responsibilities:

* **Fitting** (``_fit_booster``) happens through ``dscraft.automl.build_model``
  (LightGBM regression). It is stochastic by construction -- ``subsample`` /
  ``colsample_bytree`` draw a different row/column sample per tree -- but the
  randomness is *seeded* (``random_state``) and run in LightGBM's deterministic
  mode (``deterministic=True``, ``force_row_wise=True``), so an identical
  (data, parameters, seed) triple reproduces identical trees. dscraft is the
  only data-science backend used; this module imports it lazily so that
  ``import suiroai.modeling`` and all *inference* stays pure-stdlib.

* **Freezing** (``distill_booster``) immediately distills the fitted booster
  into a JSON-native decision-tree ensemble (splits, thresholds and leaf
  values as plain numbers) via LightGBM's own ``dump_model``. No pickled
  estimator, no ONNX blob, no runtime inference engine is persisted -- the
  frozen artifact is ordinary ``canonical()``-serializable JSON.

* **Inference** (``predict_ensemble``) is a pure-stdlib tree walker over that
  JSON. ``FittedModel.predict`` calls it; it never re-draws randomness, never
  imports dscraft, and reproduces the booster's prediction byte-for-byte. This
  is what lets ``load_model(state).predict(x) == model.predict(x)`` hold.

Quantile support: LightGBM's ``objective="quantile", alpha=tau`` fits a
genuine conditional-quantile regressor. A caller fits the median (``tau=0.5``)
for the point forecast and a higher service-level quantile (e.g. 0.95) to
drive distribution-aware safety stock downstream -- see
``replenishment/calculation.py``. The two are independent fitted models; this
module never assumes a parametric spread.

The model kind exposed through ``models.fit_model`` is ``"quantile_gbt"``.
It is only ever a shortlist *candidate*, never the mandated ``past_mean``
baseline.
"""
from __future__ import annotations

from .core import ModelingError, finite

#: Hyperparameters a caller may declare for the ``quantile_gbt`` kind. Every
#: one is forwarded verbatim into the seeded LightGBM fit; anything outside
#: this set is rejected by ``models.fit_model``'s parameter gate so a frozen
#: model can never carry an undeclared, unreproducible configuration.
QUANTILE_GBT_PARAMETERS = frozenset({
    "alpha",            # the target quantile tau in (0, 1); 0.5 == median/point
    "seed",             # recorded RNG seed -> reproducible stochastic sampling
    "n_estimators",
    "num_leaves",
    "max_depth",
    "learning_rate",
    "subsample",        # row subsampling: the stochastic part (with subsample_freq)
    "colsample_bytree",  # feature subsampling: also stochastic
    "min_child_samples",
})

#: Fixed LightGBM settings this module always imposes for reproducibility and
#: safety; they are NOT caller-configurable and are recorded in the frozen
#: state so the fit is auditable.
_FIXED_FIT_SETTINGS = {
    "objective": "quantile",
    "deterministic": True,
    "force_row_wise": True,
    "verbose": -1,
    "subsample_freq": 1,  # apply row subsampling every iteration (else ignored)
}


def _require_tabular():
    """Import dscraft's seeded GBT backend, or raise an actionable error.

    Kept lazy (call-time) so that importing/using the modeling package for
    inference never force-imports dscraft or its heavy stack. Also validates
    the environment against dscraft's known-good set up front, so a subtly
    incompatible install fails here with a clear message rather than deep
    inside LightGBM.
    """
    try:
        import dscraft
        from dscraft.automl import build_model
    except ImportError as exc:  # pragma: no cover - exercised via integration env
        raise ModelingError(
            "quantile_gbt requires the dscraft tabular backend; install "
            "suiroai with its dscraft[analytics] dependency"
        ) from exc
    dscraft.validate_environment("tabular")
    return build_model


def _quantile(parameters: dict) -> float:
    tau = finite(parameters.get("alpha", 0.5), "quantile alpha")
    if not 0.0 < tau < 1.0:
        raise ModelingError("quantile alpha must be a probability in (0, 1)")
    return tau


def _seed(parameters: dict) -> int:
    seed = parameters.get("seed", 0)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ModelingError("quantile_gbt requires a recorded nonnegative integer seed")
    return seed


def _fit_booster(training, parameters: dict):
    """Fit a seeded, stochastic LightGBM quantile regressor (dscraft backend)."""
    build_model = _require_tabular()
    width = len(training[0].features)
    # Train-only median imputation, recorded, mirroring the ridge path: a GBT
    # must still see a dense, finite matrix and we never peek outside training.
    columns = [[r.features[j] for r in training if r.features[j] is not None] for j in range(width)]
    from statistics import median
    medians = [median(col) if col else 0.0 for col in columns]
    matrix = [[medians[j] if v is None else float(finite(v)) for j, v in enumerate(r.features)]
              for r in training]
    targets = [finite(r.actual) for r in training]
    tau = _quantile(parameters)
    seed = _seed(parameters)
    kwargs = {k: parameters[k] for k in QUANTILE_GBT_PARAMETERS
              if k in parameters and k not in {"alpha", "seed"}}
    model = build_model(
        "LightGBM", "regression",
        alpha=tau, random_state=seed, **_FIXED_FIT_SETTINGS, **kwargs,
    )
    model.fit(matrix, targets)
    return model, medians, tau, seed


def distill_booster(model, *, medians, tau, seed, parameters: dict) -> dict:
    """Distill a fitted booster into JSON-native, pure-arithmetic inference state.

    The returned dict is ``canonical()``-serializable (only JSON-native numbers,
    strings, lists and dicts -- no NaN, no bytes, no pickled objects). Every
    tree is reduced to the minimal fields the stdlib walker in
    :func:`predict_ensemble` needs: split feature index, threshold, missing
    direction, and child nodes / leaf values.
    """
    dump = model.booster_.dump_model()
    trees = [_distill_node(info["tree_structure"]) for info in dump["tree_info"]]
    return {
        "kind": "quantile_gbt",
        "parameters": dict(parameters),
        "quantile": tau,
        "seed": seed,
        "medians": [finite(m, "training median") for m in medians],
        "clip_negative_forecasts": True,
        "fit_scope": "training_fold_only",
        "imputation": "training_median",
        "backend": "dscraft.automl.LightGBM",
        "objective": "quantile",
        "trees": trees,
    }


def _distill_node(node: dict) -> dict:
    """Recursively reduce one LightGBM dump node to a minimal JSON form."""
    if "leaf_value" in node:
        return {"leaf": finite(node["leaf_value"], "leaf value")}
    if node.get("decision_type") != "<=":
        # LightGBM uses "<=" for numeric splits; categorical "==" splits would
        # need a different walker and are not produced for our numeric features.
        raise ModelingError("unsupported non-numeric tree split in distilled model")
    return {
        "feature": int(node["split_feature"]),
        "threshold": finite(node["threshold"], "split threshold"),
        "default_left": bool(node["default_left"]),
        "left": _distill_node(node["left_child"]),
        "right": _distill_node(node["right_child"]),
    }


def _walk(node: dict, features) -> float:
    """Pure-arithmetic single-tree traversal. Mirrors LightGBM numeric routing."""
    while "leaf" not in node:
        value = features[node["feature"]]
        if value is None:
            node = node["left"] if node["default_left"] else node["right"]
        else:
            node = node["left"] if value <= node["threshold"] else node["right"]
    return node["leaf"]


def predict_ensemble(state: dict, features) -> float:
    """Reproduce the booster's quantile prediction from distilled JSON state.

    ``features`` is the raw example feature tuple (may contain ``None``). Train
    -only medians recorded at fit time impute missing values exactly as the fit
    saw them, so inference matches training preprocessing. The sum over trees is
    LightGBM's raw additive score; the quantile objective means this already is
    the predicted ``tau`` quantile. Negative forecasts are clamped to zero
    (gross units cannot be negative), consistent with the other model kinds.
    """
    medians = state["medians"]
    if len(features) != len(medians):
        raise ModelingError("inference feature alignment changed")
    imputed = [medians[i] if x is None else finite(x) for i, x in enumerate(features)]
    total = 0.0
    for tree in state["trees"]:
        total += _walk(tree, imputed)
    return max(0.0, finite(total, "prediction"))


def fit_quantile_gbt(training, parameters: dict) -> dict:
    """Fit + distill in one step; returns JSON-native state for ``FittedModel``."""
    model, medians, tau, seed = _fit_booster(training, parameters)
    return distill_booster(model, medians=medians, tau=tau, seed=seed, parameters=parameters)
