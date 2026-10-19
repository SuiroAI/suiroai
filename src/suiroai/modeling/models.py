"""Small deterministic reference candidates, serializable without pickle.

Ridge uses training-only median imputation and standardization. This bounded
small-feature implementation avoids adding dependencies to shared manifests.

Provide bounded reference candidates whose fitted preprocessing can be
retained with the selected model, keeping learned transforms training-only.

Linear: https://linear.app/gr3enarr0w/issue/DSC-28
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from statistics import fmean, median

from .core import ModelingError, canonical, finite


def _solve(a, b):
    n = len(b)
    work = [list(row) + [value] for row, value in zip(a, b)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(work[i][col]))
        work[col], work[pivot] = work[pivot], work[col]
        if abs(work[col][col]) < 1e-12:
            raise ModelingError("unidentifiable regression system")
        scale = work[col][col]
        work[col] = [v / scale for v in work[col]]
        for row in range(n):
            if row != col:
                scale = work[row][col]
                work[row] = [v-scale*w for v,w in zip(work[row],work[col])]
    return [finite(row[-1], "fitted coefficient") for row in work]


@dataclass(frozen=True)
class FittedModel:
    """Immutable bytes; .payload returns a detached copy for artifact storage."""
    state: bytes

    def payload(self):
        return json.loads(self.state)

    def predict(self, example):
        p = self.payload()
        if p["kind"] == "past_mean":
            key = list(example.window.key) + [example.window.horizon_days]
            match = [r["value"] for r in p["series_means"] if r["key"] == key]
            if len(match) != 1:
                raise ModelingError("baseline population lacks past-only training evidence")
            return match[0]
        if p["kind"] == "mean":
            return p["intercept"]
        if len(example.features) != len(p["medians"]):
            raise ModelingError("inference feature alignment changed")
        values = [(p["medians"][i] if x is None else finite(x)) for i,x in enumerate(example.features)]
        z = [(x-p["centers"][i])/p["scales"][i] for i,x in enumerate(values)]
        value = p["intercept"] + sum(a*b for a,b in zip(p["coefficients"], z))
        return max(0.0, finite(value, "prediction"))


def fit_model(kind, training, parameters=None):
    rows = tuple(training)
    parameters = dict(parameters or {})
    if not rows or len(rows) > 100000:
        raise ModelingError("empty or unbounded training population")
    widths = {len(r.features) for r in rows}
    if len(widths) != 1:
        raise ModelingError("training feature alignment changed")
    if kind not in {"past_mean", "mean", "ridge"}:
        raise ModelingError("unsupported bounded model candidate")
    if set(parameters) - ({"alpha"} if kind == "ridge" else set()):
        raise ModelingError("undeclared model configuration")
    p = {"kind": kind, "parameters": parameters, "training_count": len(rows),
         "training_target_end_max": max(r.window.end for r in rows).isoformat(),
         "training_information_end_max": max(r.label_available_on for r in rows).isoformat(),
         "clip_negative_forecasts": True}
    if kind == "past_mean":
        keys = sorted({(r.window.key, r.window.horizon_days) for r in rows})
        p["baseline_label"] = "past-only historical-horizon mean demo comparator; not verified customer process"
        p["series_means"] = [{"key": list(k)+[h], "value": fmean(r.actual for r in rows if r.window.key == k and r.window.horizon_days == h)} for k,h in keys]
    else:
        ybar = fmean(r.actual for r in rows)
        p["intercept"] = ybar
        if kind == "ridge":
            alpha = finite(parameters.get("alpha", 1.0), "ridge alpha")
            if alpha <= 0:
                raise ModelingError("ridge alpha must be positive and predeclared")
            width = len(rows[0].features)
            if width < 1:
                raise ModelingError("ridge requires prepared features")
            columns = [[r.features[j] for r in rows if r.features[j] is not None] for j in range(width)]
            # Explicit train-only zero for an entirely absent feature, recorded.
            medians = [median(col) if col else 0.0 for col in columns]
            x = [[medians[j] if v is None else float(v) for j,v in enumerate(r.features)] for r in rows]
            centers = [fmean(row[j] for row in x) for j in range(width)]
            scales = [(fmean((row[j]-centers[j])**2 for row in x)**0.5 or 1.0) for j in range(width)]
            z = [[(v-centers[j])/scales[j] for j,v in enumerate(row)] for row in x]
            a = [[sum(row[j]*row[k] for row in z) + (alpha if j == k else 0.0) for k in range(width)] for j in range(width)]
            b = [sum(row[j]*(r.actual-ybar) for row,r in zip(z, rows)) for j in range(width)]
            p.update(medians=medians, centers=centers, scales=scales,
                     coefficients=_solve(a,b), all_missing_training_columns=[j for j,col in enumerate(columns) if not col],
                     fit_scope="training_fold_only", imputation="training_median", standardization="training_mean_population_std")
    return FittedModel(canonical(p))


def load_model(payload):
    """Load trusted measured JSON; never deserialize executable model objects."""
    if not isinstance(payload, dict) or payload.get("kind") not in {"ridge", "mean", "past_mean"}:
        raise ModelingError("unknown saved model format")
    return FittedModel(canonical(payload))
