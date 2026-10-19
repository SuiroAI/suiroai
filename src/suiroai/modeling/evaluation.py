"""Development-only, bounded measured evaluation; DSC-10 owns checkpoint decisions.

These private calculation objects are not replacement DSC-24 wire contracts.
A caller supplies prepared, availability-checked examples, never the raw sales file.

Support step6 baseline evaluation and step8 comparison on matching windows,
populations, and metrics within a finite development budget; parent review
retains the better, worse, or equal branch decision.

Linear: https://linear.app/gr3enarr0w/issue/DSC-28
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from time import monotonic
from typing import Mapping, Sequence

from .core import CUTOFF, Example, ModelingError, Prediction
from .metrics import compare_values, metric_value, score
from .models import fit_model


@dataclass(frozen=True)
class RollingFold:
    fold_id: str
    training: tuple[Example, ...]
    validation: tuple[Example, ...]
    training_end: date | None = None


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    model_kind: str
    feature_set_id: str
    parameters: Mapping
    rationale: str


def _validate_folds(folds):
    folds = tuple(folds)
    if not folds or len({f.fold_id for f in folds}) != len(folds):
        raise ModelingError("development folds must be nonempty with unique IDs")
    seen = set()
    width = None
    for fold in folds:
        if not fold.fold_id or not fold.training or not fold.validation:
            raise ModelingError("each named fold needs training and validation examples")
        if len({e.window for e in fold.training}) != len(fold.training):
            raise ModelingError("duplicate training windows")
        origins = {e.window.origin for e in fold.validation}
        if len(origins) != 1:
            raise ModelingError("each development fold must have one common forecast origin")
        origin = next(iter(origins))
        training_end = fold.training_end or origin
        if type(training_end) is not date or training_end > origin:
            raise ModelingError("training cutoff cannot follow the forecast origin")
        for example in (*fold.training, *fold.validation):
            if example.window.end > CUTOFF or example.label_available_on > CUTOFF:
                raise ModelingError("development labels must be available by November 30")
            if width is None:
                width = len(example.features)
            if len(example.features) != width:
                raise ModelingError("feature width must be stable within one feature option")
        if any(e.window.start < date(2022, 1, 1) for e in fold.training):
            raise ModelingError("training targets cannot precede permitted 2022 history")
        if any(e.window.start < date(2025, 1, 1) for e in fold.validation):
            raise ModelingError("rolling validation targets must be in 2025 development")
        if any(e.window.end > training_end or e.label_available_on > training_end
               for e in fold.training):
            raise ModelingError("training labels must be fully observed and available at the training cutoff")
        eligible = {(e.window.key, e.window.horizon_days) for e in fold.training}
        for example in fold.validation:
            if (example.window.key, example.window.horizon_days) not in eligible:
                raise ModelingError("validation key/horizon lacks past-only training evidence")
            if example.window in seen:
                raise ModelingError("duplicate development validation window")
            seen.add(example.window)
    return folds


def _signature(folds):
    """Actual labels and all fold bindings must match across feature options."""
    return tuple((f.fold_id, f.training_end,
                  tuple(sorted((e.window, e.actual, e.label_available_on) for e in f.training)),
                  tuple(sorted((e.window, e.actual, e.label_available_on) for e in f.validation)))
                 for f in folds)


def _spec(spec):
    if (not spec.candidate_id or not spec.feature_set_id or not spec.rationale.strip()
            or spec.model_kind not in {"past_mean", "mean", "ridge"}
            or not isinstance(spec.parameters, Mapping)):
        raise ModelingError("candidate needs a supported model, feature ID and justified rationale")
    return {"candidate_id": spec.candidate_id, "model_kind": spec.model_kind,
            "feature_set_id": spec.feature_set_id, "parameters": dict(spec.parameters),
            "rationale": spec.rationale}


class _Budget:
    def __init__(self, fits, max_fits, max_seconds):
        if type(max_fits) is not int or max_fits < fits:
            raise ModelingError("declared fit budget cannot cover the complete measured shortlist")
        if (isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float))
                or not isfinite(max_seconds) or max_seconds <= 0):
            raise ModelingError("a finite positive runtime limit is required")
        self.started = monotonic()
        self.seconds = max_seconds
        self.used_fits = 0

    def check(self):
        if monotonic() - self.started > self.seconds:
            raise ModelingError("development evaluation runtime budget exhausted; partial scores are diagnostic only")


def _measure(spec, folds, population_id, budget, include_wape):
    metadata = _spec(spec)
    predictions, fitted = [], []
    for fold in folds:
        budget.check()
        # Learned imputation/scaling and coefficients are fitted on this tuple only.
        model = fit_model(spec.model_kind, fold.training, dict(spec.parameters))
        budget.used_fits += 1
        budget.check()
        for example in fold.validation:
            predictions.append(Prediction(example.window, example.actual, model.predict(example)))
            budget.check()
        fitted.append({"fold_id": fold.fold_id,
                       "training_end": (fold.training_end or fold.validation[0].window.origin).isoformat(),
                       "model": model.payload()})
    measured = score(predictions, population_id, include_wape=include_wape)
    return {**metadata, **measured, "predictions": [p.payload() for p in predictions],
            "fitted_folds": fitted, "fit_count": len(folds), "eligible_for_selection": True}


def evaluate_initial(folds: Sequence[RollingFold], baseline: CandidateSpec,
                     initial: CandidateSpec, *, population_id: str,
                     primary_metric_id="mae", direction="lower_is_better", tolerance=0.0,
                     max_fits=8, max_seconds=60.0, include_wape=False):
    """Measure one initial model and an honestly labeled past-only demo comparator.

    Better/equal/worse is numerical evidence for a parent decision; no continuation
    authorization is granted here, even when the initial candidate is better.
    """
    folds = _validate_folds(folds)
    _spec(baseline)
    _spec(initial)
    compare_values(0, 0, direction, tolerance)
    if (baseline.model_kind != "past_mean" or baseline.candidate_id == initial.candidate_id
            or baseline.feature_set_id != initial.feature_set_id):
        raise ModelingError("initial evaluation requires distinct candidates on the same initial features and a past_mean baseline")
    budget = _Budget(2 * len(folds), max_fits, max_seconds)
    baseline_result = _measure(baseline, folds, population_id, budget, include_wape)
    initial_result = _measure(initial, folds, population_id, budget, include_wape)
    comparison = compare_values(metric_value(baseline_result, primary_metric_id),
                                metric_value(initial_result, primary_metric_id), direction, tolerance)
    return {"baseline": baseline_result, "initial": initial_result,
            "baseline_label": "Past-only historical mean demo comparator; not the customer's actual process.",
            "primary_metric_id": primary_metric_id, "direction": direction,
            "tie_tolerance": tolerance, "comparison": comparison,
            "requires_parent_review": comparison != "better", "parent_verified": False,
            "fit_count": budget.used_fits, "development_cutoff": CUTOFF.isoformat()}


def compare_candidates(options: Mapping[str, Sequence[RollingFold]],
                       candidates: Sequence[CandidateSpec], *, population_id: str,
                       primary_metric_id="mae", direction="lower_is_better", tolerance=0.0,
                       max_candidates=6, max_fits=24, max_seconds=60.0,
                       include_wape=False):
    """Evaluate a predeclared shortlist on identical folds and retain all results.

    A proposed feature earns inclusion only through measured comparison. Ties keep
    the earlier predeclared candidate, so put the original-feature reference first.
    The caller must bind the shortlist/plan before this function and freeze the
    measured winner separately before final data can be released.
    """
    candidates = tuple(candidates)
    if (type(max_candidates) is not int or not 1 <= len(candidates) <= max_candidates
            or len({c.candidate_id for c in candidates}) != len(candidates)):
        raise ModelingError("shortlist must be nonempty, uniquely named and within the candidate budget")
    compare_values(0, 0, direction, tolerance)
    for candidate in candidates:
        _spec(candidate)
    used_options = {c.feature_set_id for c in candidates}
    if not used_options <= options.keys():
        raise ModelingError("candidate feature option is missing")
    folds = {name: _validate_folds(options[name]) for name in sorted(used_options)}
    reference = next(iter(folds.values()))
    if any(_signature(option) != _signature(reference) for option in folds.values()):
        raise ModelingError("feature options must use equal populations, origins, horizons, labels and folds")
    budget = _Budget(len(candidates) * len(reference), max_fits, max_seconds)
    results = [_measure(candidate, folds[candidate.feature_set_id], population_id, budget, include_wape)
               for candidate in candidates]
    winner = results[0]
    for result in results[1:]:
        if compare_values(metric_value(winner, primary_metric_id),
                          metric_value(result, primary_metric_id), direction, tolerance) == "better":
            winner = result
    return {"candidates": results, "selected_candidate_id": winner["candidate_id"],
            "selected_feature_set_id": winner["feature_set_id"],
            "primary_metric_id": primary_metric_id, "direction": direction,
            "tie_tolerance": tolerance, "tie_rule": "earlier_predeclared_candidate",
            "parent_verified": False, "fit_count": budget.used_fits,
            "development_cutoff": CUTOFF.isoformat()}
