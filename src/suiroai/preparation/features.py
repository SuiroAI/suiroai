"""Small initial feature recipe; no outcome lags without availability evidence.

Calendar values are known in advance. Identifiers are encoded by a frozen
training-fold vocabulary, never by a full-development/holdout fit.

Support initial features before model evaluation using prediction-time
information and training-fold preprocessing, without leaking future outcomes.

Linear: https://linear.app/gr3enarr0w/issue/DSC-27
"""
from dataclasses import dataclass
from datetime import date, timedelta

from .worker import CUTOFF, START, KEYS, PreparationError, calendar, key

FEATURE_NAMES = ("target_weekday", "target_month", "target_day_of_year", "target_weekend")


def _calendar_features(day):
    return dict(zip(FEATURE_NAMES, (day.weekday(), day.month, day.timetuple().tm_yday, int(day.weekday() >= 5))))


def check_daily_grain(daily):
    seen = set()
    for row in daily:
        identity = (*key(row), calendar(row["Order_Date"]))
        if identity in seen:
            raise PreparationError("wrong grain: duplicate product/store/day")
        seen.add(identity)
        if row.get("observed_record_day") is not True:
            raise PreparationError("daily record lacks observation mask")
        if type(row.get("target_quantity")) is not int or row["target_quantity"] < 0:
            raise PreparationError("invalid recorded daily Quantity target")


def build_features(daily, *, source_namespace, operational_keys=()):
    """Historical rows have prior-day origin; no fitted transformation here.

    origin_rows is the separate key-only November 30 prediction population.
    It contains no December targets or values. No lag, status, return, revenue,
    inventory, realized customer delivery, or observation-mask predictor is used.
    """
    check_daily_grain(daily)
    rows = []
    first_seen = {}
    for r in daily:
        k = key(r)
        first_seen[k] = min(first_seen.get(k, r["Order_Date"]), r["Order_Date"])
    for r in daily:
        d = date.fromisoformat(r["Order_Date"])
        if not START <= d.isoformat() <= CUTOFF:
            raise PreparationError("future/out-of-scope initial feature row")
        if first_seen[key(r)] >= d.isoformat():
            continue  # A future order cannot create a known forecast population.
        rows.append({"source_namespace": source_namespace, **{k: r[k] for k in KEYS},
            "origin": (d-timedelta(days=1)).isoformat(), "target_date": d.isoformat(),
            **_calendar_features(d)})
    validate_feature_rows(rows)
    keys = sorted(set(tuple(k) for k in operational_keys) or {key(r) for r in daily})
    return {"format": "dsc27-initial-v1", "source_namespace": source_namespace,
        "rows": rows, "origin_rows": [{"source_namespace": source_namespace,
            **dict(zip(KEYS, k)), "origin": CUTOFF} for k in keys],
        "predictor_columns": [*KEYS, *FEATURE_NAMES],
        "excluded_unseen_key_target_rows": len(daily)-len(rows),
        "population_rule": "Key must have a transaction strictly before origin's target day; first observed day omitted",
        "no_fitted_transformations": True,
        "target_availability": "Retrospective recorded units only; status and return latency unknown. Never lag this target without separate origin-time availability evidence."}


def validate_feature_rows(rows):
    allowed = {"source_namespace", *KEYS, "origin", "target_date", *FEATURE_NAMES}
    seen = set()
    for row in rows:
        if set(row) != allowed:
            raise PreparationError("unknown/unapproved predictor; possible future feature leakage")
        d = date.fromisoformat(calendar(row["target_date"]))
        origin = calendar(row["origin"])
        if not START <= d.isoformat() <= CUTOFF or origin >= d.isoformat():
            raise PreparationError("feature origin/target boundary invalid")
        if any(type(row[n]) is not int or row[n] != v for n, v in _calendar_features(d).items()):
            raise PreparationError("initial features differ from deterministic calendar definition")
        ident = (row["source_namespace"], *key(row), origin, d.isoformat())
        if ident in seen:
            raise PreparationError("wrong feature grain")
        seen.add(ident)


@dataclass(frozen=True)
class CategoryTransform:
    """Immutable fold-specific learned state; unknown IDs encode to -1."""
    training_end: str
    validation_start: str
    products: tuple[str, ...]
    stores: tuple[str, ...]


def fit_categories(training_rows, *, training_end, validation_start):
    calendar(training_end)
    calendar(validation_start)
    validate_feature_rows(training_rows)
    if not training_rows or training_end >= validation_start or training_end > CUTOFF:
        raise PreparationError("invalid training-fold boundaries")
    # The last label date, not just the origin, must precede validation.
    if any(r["target_date"] > training_end or r["origin"] >= validation_start for r in training_rows):
        raise PreparationError("training-fold transform received validation/future records")
    return CategoryTransform(training_end, validation_start,
        tuple(sorted({r["Product_ID"] for r in training_rows})),
        tuple(sorted({r["Store_ID"] for r in training_rows})))


def transform_categories(rows, fitted):
    validate_feature_rows(rows)
    products = {v: i for i, v in enumerate(fitted.products)}
    stores = {v: i for i, v in enumerate(fitted.stores)}
    return [{**r, "product_code": products.get(r["Product_ID"], -1),
             "store_code": stores.get(r["Store_ID"], -1)} for r in rows]


def horizon_target(daily, *, product_id, store_id, origin, horizon_days, end_cutoff=CUTOFF):
    """No horizon target if any day is absent/incomplete or extends past cutoff.

    complete_daily_sales cannot be established by this source's global dates.
    A future completeness-supported adapter must provide evidence, not flip a
    missing-date switch. The present prepared fixture remains explicitly false.
    """
    check_daily_grain(daily)
    calendar(origin)
    if type(horizon_days) is not int or horizon_days < 1:
        raise PreparationError("invalid target horizon")
    end = date.fromisoformat(origin) + timedelta(days=horizon_days)
    if end.isoformat() > min(calendar(end_cutoff), CUTOFF):
        return None
    rows = {r["Order_Date"]: r for r in daily if key(r) == (product_id, store_id)}
    selected = []
    for offset in range(1, horizon_days+1):
        r = rows.get((date.fromisoformat(origin)+timedelta(days=offset)).isoformat())
        if (r is None or r.get("complete_daily_sales") is not True
                or not r.get("completeness_evidence_refs")):
            return None
        selected.append(r["target_quantity"])
    return sum(selected)
