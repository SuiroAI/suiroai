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

#: Hyperparameters a caller may declare for the ``quantile_gbt`` kind. Every one
#: is forwarded verbatim into dscraft's first-party seeded quantile fit; anything
#: outside this set is rejected by ``models.fit_model``'s parameter gate so a
#: frozen model can never carry an undeclared, unreproducible configuration.
#:
#: FIRST-PARTY RECONCILIATION: this previously targeted LightGBM via
#: ``build_model("LightGBM", objective="quantile", ...)``. dscraft's first-party
#: rebuild removed LightGBM, so the quantile capability is now dscraft's own
#: ``DSQuantileBoost`` backend, consumed here through the public
#: ``dscraft.automl.fit_quantile_model`` / serialized-inference contract -- no
#: third-party backend, no ``booster_.dump_model()`` internal, no private attrs.
QUANTILE_GBT_PARAMETERS = frozenset({
    "alpha",            # the target quantile tau in (0, 1); 0.5 == median/point
    "seed",             # recorded RNG seed -> reproducible stochastic sampling
    "n_estimators",
    "max_depth",
    "learning_rate",
    "subsample",        # row subsampling: the stochastic part
})


def _require_quantile_backend():
    """Import dscraft's first-party quantile contract, or raise an actionable error.

    Kept lazy (call-time) so that importing/using the modeling package for
    inference never force-imports dscraft or its heavy stack. Also validates the
    environment against dscraft's known-good set up front, so a subtly
    incompatible install fails here with a clear message.
    """
    try:
        import dscraft
        from dscraft.automl import fit_quantile_model, predict_from_serialized
    except ImportError as exc:  # pragma: no cover - exercised via integration env
        raise ModelingError(
            "quantile_gbt requires the dscraft tabular backend; install "
            "suiroai with its dscraft[analytics] dependency"
        ) from exc
    dscraft.validate_environment("tabular")
    return fit_quantile_model, predict_from_serialized


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


def _prepare(training, parameters: dict):
    """Train-only median imputation into a dense finite matrix (never peeks outside training)."""
    width = len(training[0].features)
    columns = [[r.features[j] for r in training if r.features[j] is not None] for j in range(width)]
    from statistics import median
    medians = [median(col) if col else 0.0 for col in columns]
    matrix = [[medians[j] if v is None else float(finite(v)) for j, v in enumerate(r.features)]
              for r in training]
    targets = [finite(r.actual) for r in training]
    return matrix, targets, medians


def fit_quantile_gbt(training, parameters: dict) -> dict:
    """Fit a seeded first-party quantile model via dscraft and distill to JSON state.

    Returns a ``canonical()``-serializable dict (JSON-native numbers/strings/lists/dicts;
    no NaN, no bytes, no pickled objects). The distilled ``model`` payload is dscraft's own
    ``ds_quantile_v1`` serialization (a JSON tree ensemble), so inference is a pure-arithmetic
    tree walk that never imports dscraft or any training backend.
    """
    fit_quantile_model, _ = _require_quantile_backend()
    matrix, targets, medians = _prepare(training, parameters)
    tau = _quantile(parameters)
    seed = _seed(parameters)
    kwargs = {k: parameters[k] for k in QUANTILE_GBT_PARAMETERS
              if k in parameters and k not in {"alpha", "seed"}}
    model = fit_quantile_model(matrix, targets, quantiles=(tau,), seed=seed, **kwargs)
    import json as _json
    serialized = _json.loads(model.serialize().decode("utf-8"))
    return {
        "kind": "quantile_gbt",
        "parameters": dict(parameters),
        "quantile": tau,
        "seed": seed,
        "medians": [finite(m, "training median") for m in medians],
        "clip_negative_forecasts": True,
        "fit_scope": "training_fold_only",
        "imputation": "training_median",
        "backend": "dscraft.automl.DSQuantileBoost",
        "objective": "quantile",
        # dscraft's ds_quantile_v1 JSON payload (the model itself, not a refit recipe).
        "ds_quantile_model": serialized,
    }


def _walk_tree(node: dict, features) -> float:
    """Pure-stdlib single-tree traversal over a distilled ds_quantile_v1 node."""
    while "leaf" not in node:
        node = node["left"] if features[node["feature"]] <= node["threshold"] else node["right"]
    return node["leaf"]


def predict_ensemble(state: dict, features) -> float:
    """Reproduce the quantile prediction from distilled JSON state (pure stdlib).

    ``features`` is the raw example feature tuple (may contain ``None``). Train-only medians
    recorded at fit time impute missing values exactly as the fit saw them, so inference matches
    training preprocessing. The tree walk is pure stdlib arithmetic over the stored
    ``ds_quantile_v1`` JSON ensemble -- it deliberately does NOT import dscraft, so loading and
    predicting a frozen model never pulls in the training backend or its heavy dependencies
    (this preserves the no-pickle, stdlib-only inference guarantee). The single stored quantile's
    ensemble is summed as ``init + learning_rate * sum(tree)``; negatives are clamped to zero
    (gross units cannot be negative), consistent with the other model kinds.
    """
    medians = state["medians"]
    if len(features) != len(medians):
        raise ModelingError("inference feature alignment changed")
    imputed = [medians[i] if x is None else float(finite(x)) for i, x in enumerate(features)]
    tau = float(state["quantile"])
    model = state["ds_quantile_model"]
    ensembles = model.get("ensembles") or {}
    # single-quantile model: find the ensemble whose key parses to tau
    ens = None
    for key, candidate in ensembles.items():
        try:
            if abs(float(key) - tau) < 1e-12:
                ens = candidate
                break
        except (TypeError, ValueError):
            continue
    if ens is None:
        raise ModelingError("distilled quantile ensemble missing for the recorded quantile")
    if len(imputed) != ens["n_features_in"]:
        raise ModelingError("inference feature alignment changed")
    total = ens["init"] + ens["learning_rate"] * sum(_walk_tree(t, imputed) for t in ens["trees"])
    return max(0.0, finite(total, "prediction"))
