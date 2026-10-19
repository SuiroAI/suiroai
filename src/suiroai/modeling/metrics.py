"""Common comparable metrics. No MAPE and no cross-SKU pooled WAPE.

Compute comparable forecast errors and direction-aware candidate comparisons
while enforcing population, aggregation, and same-product unit constraints.
"""
from collections import defaultdict
from statistics import fmean

from .core import ModelingError, finite, prediction_signature


def compare_values(baseline, candidate, direction="lower_is_better", tolerance=0.0):
    tolerance = finite(tolerance, "tie tolerance")
    if tolerance < 0 or direction not in {"lower_is_better", "higher_is_better"}:
        raise ModelingError("invalid comparison direction/tolerance")
    improvement = finite(baseline) - finite(candidate)
    if direction == "higher_is_better":
        improvement *= -1
    return "equal" if abs(improvement) <= tolerance else "better" if improvement > 0 else "worse"


def score(predictions, population_id, *, include_wape=False):
    rows = tuple(predictions)
    prediction_signature(rows)
    if not population_id:
        raise ModelingError("metric population must be named")
    groups = defaultdict(list)
    for row in rows:
        groups[row.window.key].append(row)
    per_series = []
    for key, group in sorted(groups.items()):
        errors = [r.predicted - r.actual for r in group]
        per_series.append({"key": list(key), "mae": fmean(map(abs, errors)),
                           "bias": fmean(errors), "observation_count": len(group)})
    common = {"unit": "product_unit", "population_id": population_id,
              "observation_count": len(rows),
              "forecast_origin_start": min(r.window.origin for r in rows).isoformat(),
              "forecast_origin_end": max(r.window.origin for r in rows).isoformat(),
              "target_end_max": max(r.window.end for r in rows).isoformat()}
    # Equal series weighting is deliberate: busy series cannot hide sparse ones.
    scores = [dict(common, metric_id="mae", value=fmean(g["mae"] for g in per_series)),
              dict(common, metric_id="bias", value=fmean(g["bias"] for g in per_series))]
    if include_wape:
        if len({r.window.key[:2] for r in rows}) != 1:
            raise ModelingError("WAPE pooling requires the same namespace and SKU/product units")
        denominator = sum(r.actual for r in rows)
        if denominator <= 0:
            raise ModelingError("WAPE is undefined with zero actual units")
        scores.append(dict(common, metric_id="wape", unit="ratio",
                           value=sum(abs(r.predicted-r.actual) for r in rows)/denominator))
    return {"scores": scores, "per_series": per_series,
            "aggregation": "equal_series_mean", "bias_sign": "prediction_minus_actual",
            "limitations": ["Forecast accuracy alone does not establish stockout, profit or inventory-cost improvement.",
                            "Overlapping horizons are dependent; no significance claim is made."]}


def metric_value(result, metric_id="mae"):
    matches = [s for s in result["scores"] if s["metric_id"] == metric_id]
    if len(matches) != 1:
        raise ModelingError("expected exactly one declared metric")
    return matches[0]["value"]
