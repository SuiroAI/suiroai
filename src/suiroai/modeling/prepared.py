"""Consumer of agreed DSC-27 payloads, without reading raw source files.

Completeness and target availability are evidence, not inferred from date
coverage. Current sparse DSC-27 output cannot support complete demand labels.

Connect safe preparation to evaluation without deriving daily completeness
from sparse observations, and exclude development target horizons that cross
into the reserved December holdout.

Linear: https://linear.app/gr3enarr0w/issue/DSC-28
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
import math

from suiroai.contracts import digest, record_ref, validate_record
from .core import CUTOFF, Example, ModelingError, Window, finite, require_parent


def _read_json(store, ref):
    try:
        return json.loads(store.read_bytes(ref))
    except (ValueError, OSError) as exc:
        raise ModelingError("unavailable or invalid measured JSON artifact") from exc


def read_development(store, preparation, execution):
    """Read exact approved development reference; no ambient path or holdout read."""
    for record in (preparation, execution):
        errors = validate_record(record)
        if errors:
            raise ModelingError(errors[0])
    if preparation["binding"] != execution["binding"] or preparation["run_id"] != execution["run_id"]:
        raise ModelingError("preparation changed task/run/input/proposal binding")
    if preparation["execution_contract_ref"] != record_ref(execution):
        raise ModelingError("preparation belongs to a different execution contract")
    require_parent(preparation["parent_decision"], "preparation")
    ref = preparation["prepared_development_data_ref"]
    if ref not in preparation["development_context_allowlist"]:
        raise ModelingError("development data is not in the approved context allowlist")
    metadata = [a for a in preparation["availability"] if a["artifact_ref"] == ref]
    if len(metadata) != 1:
        raise ModelingError("development availability metadata is ambiguous")
    a = metadata[0]
    if (a["permitted_use"] != "development" or a["contains_post_cutoff_rows"]
            or max(a["latest_event_date"], a["latest_information_available_date"]) > CUTOFF.isoformat()):
        raise ModelingError("future data cannot enter modeling context")
    payload = _read_json(store, ref)
    return DailyView.from_payload(payload)


@dataclass(frozen=True)
class DailyView:
    """Immutable daily artifact bytes; null/missing dates stay unknown."""
    state: bytes

    @classmethod
    def from_payload(cls, payload):
        from .core import canonical
        if payload.get("format") != "dsc27-daily-v1" or not payload.get("source_namespace"):
            raise ModelingError("unsupported DSC-27 daily payload")
        seen = set()
        for row in payload["rows"]:
            key = (payload["source_namespace"], row["Product_ID"], row["Store_ID"])
            day = date.fromisoformat(row["Order_Date"])
            if not date(2022,1,1) <= day <= CUTOFF:
                raise ModelingError("development row outside permitted chronology")
            if (key, day) in seen:
                raise ModelingError("duplicate daily prepared key")
            seen.add((key,day))
            if row["target_quantity"] is not None and finite(row["target_quantity"], "prepared quantity") < 0:
                raise ModelingError("negative prepared gross-unit target")
            if type(row.get("complete_daily_sales")) is not bool or type(row.get("observed_record_day")) is not bool:
                raise ModelingError("prepared observations require explicit completeness flags")
        return cls(canonical(payload))

    @property
    def payload(self):
        return json.loads(self.state)

    def horizon_target(self, window: Window):
        p = self.payload
        if window.key[0] != p["source_namespace"] or window.end > CUTOFF:
            raise ModelingError("development target crosses scope/cutoff")
        rows = {r["Order_Date"]: r for r in p["rows"]
                if (r["Product_ID"], r["Store_ID"]) == window.key[1:]}
        total = 0.0
        availability = []
        for offset in range(1, window.horizon_days+1):
            day = window.origin + timedelta(days=offset)
            row = rows.get(day.isoformat())
            if (not row or row["target_quantity"] is None or not row["complete_daily_sales"]
                    or not (row.get("completeness_evidence_refs") or p.get("completeness_evidence_refs"))):
                raise ModelingError("unavailable full-horizon demand: missing/completeness evidence; missing dates are not zero")
            if not row.get("target_available_date"):
                raise ModelingError("target availability is unknown; training labels cannot assume immediate availability")
            available = date.fromisoformat(row["target_available_date"])
            if available < day or available > CUTOFF:
                raise ModelingError("target availability outside development chronology")
            availability.append(available)
            total += finite(row["target_quantity"])
        return total, max(availability)


def build_examples(view, feature_rows, feature_fields, windows):
    """Feature values must be defined and available at each forecast origin."""
    feature_fields = tuple(feature_fields)
    if not feature_fields or len(set(feature_fields)) != len(feature_fields):
        raise ModelingError("initial feature fields must be unique and nonempty")
    namespace = view.payload["source_namespace"]
    aligned = {}
    for row in feature_rows:
        key = (row.get("source_namespace", namespace), row["Product_ID"], row["Store_ID"])
        origin = date.fromisoformat(row["origin"])
        if origin > CUTOFF:
            raise ModelingError("future feature origin")
        if not row.get("latest_information_available_date") and not set(feature_fields) <= {"year","month","quarter","day_of_week","day_of_year","week_of_year","is_weekend","target_weekday","target_month","target_day_of_year","target_weekend"}:
            raise ModelingError("noncalendar feature availability is unknown")
        if row.get("latest_information_available_date", origin.isoformat()) > origin.isoformat():
            raise ModelingError("feature unavailable at prediction origin")
        if (key,origin) in aligned:
            raise ModelingError("duplicate feature alignment")
        aligned[key,origin] = row
    examples = []
    for window in windows:
        row = aligned.get((window.key,window.origin))
        if row is None or any(name not in row for name in feature_fields):
            raise ModelingError("missing original feature row/field")
        target, available = view.horizon_target(window)
        examples.append(Example(window, tuple(row[f] for f in feature_fields), target, available))
    return tuple(examples)


def forecast_daily_rows(raw_bytes):
    """DSC-29/30 adapter: verify producer trajectory; never split an aggregate.

    Caller measures the artifact reference and validates final/parent authority.
    This function only checks immutable saved bytes, identity and arithmetic.
    """
    try:
        p = json.loads(raw_bytes)
        rows = p.get("daily_forecast", [])
        horizons = p["rows"]
        if not rows or not p.get("recommendation_ready"):
            raise ModelingError("saved forecast has no verified explicit daily trajectory")
        if not p.get("binding") or not p.get("run_id"):
            raise ModelingError("forecast lacks task/run/version binding")
        parsed = {}
        for row in rows:
            k = row["key"]
            key = (k["source_namespace"],k["product_id"],k["store_id"])
            day = date.fromisoformat(row["date"])
            if (row["quantity_unit"] != "product_unit" or row["as_of_date"] != CUTOFF.isoformat()
                    or row["latest_information_available_date"] > CUTOFF.isoformat()
                    or not CUTOFF < day <= date(2025,12,31) or (key,day) in parsed):
                raise ModelingError("invalid saved daily forecast timing/unit/alignment")
            quantity = finite(row["quantity"], "daily forecast")
            if quantity < 0:
                raise ModelingError("negative saved daily forecast")
            parsed[key,day] = quantity
        expected = set()
        seen = set()
        for horizon in horizons:
            key = tuple(horizon["key"])
            window = Window(key,date.fromisoformat(horizon["origin"]),horizon["horizon_days"])
            if window.origin != CUTOFF or window.end > date(2025,12,31) or window in seen:
                raise ModelingError("saved horizon is not unique complete November30 forecast")
            seen.add(window)
            keys = [(key,window.start+timedelta(days=i)) for i in range(window.horizon_days)]
            expected.update(keys)
            if any(k not in parsed for k in keys) or not math.isclose(sum(parsed[k] for k in keys),finite(horizon["predicted"]),rel_tol=1e-9,abs_tol=1e-9):
                raise ModelingError("daily trajectory differs from frozen evaluated horizon total")
        if set(parsed) != expected or not expected:
            raise ModelingError("daily trajectory has unmatched population/dates")
        return json.loads(json.dumps(rows))
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ModelingError):
            raise
        raise ModelingError("invalid saved forecast payload") from exc


def materialize_reserved_targets(store, *, bundle_ref, reserved_unseen_data_ref,
                                 stage_request, artifact_id, observed_through):
    """Derive verified whole-horizon labels only after the frozen-stage release.

    Missing or incomplete daily observations remain explicit coverage exclusions.
    Both original source and derived numerical target refs are retained.
    """
    from .core import canonical, checked_definition, utc_time
    from .frozen import verify_frozen, reserved_actuals_payload, _window
    bundle, _, forecast = verify_frozen(store,bundle_ref)
    checked_definition("stage_request",stage_request)
    require_parent(stage_request["parent_authorization"],"final_validation")
    if (stage_request["stage"] != "final_validation"
            or stage_request["binding"] != bundle["binding"] or stage_request["run_id"] != bundle["run_id"]
            or stage_request["execution_contract_ref"]["sha256"] != bundle["execution_contract_sha256"]
            or reserved_unseen_data_ref not in stage_request["released_input_refs"]
            or utc_time(stage_request["issued_at"]) <= utc_time(bundle["frozen"]["frozen_at"])):
        raise ModelingError("reserved targets require exact authorized post-freeze release")
    if type(observed_through) is not date or not CUTOFF < observed_through <= date(2025,12,31):
        raise ModelingError("reserved observation cutoff outside December")
    p=_read_json(store,reserved_unseen_data_ref)
    if p.get("format") != "dsc27-daily-v1":
        raise ModelingError("unsupported reserved DSC-27 artifact")
    daily={}
    for row in p["rows"]:
        day=date.fromisoformat(row["Order_Date"])
        key=(p["source_namespace"],row["Product_ID"],row["Store_ID"])
        if not CUTOFF < day <= date(2025,12,31) or (key,day) in daily:
            raise ModelingError("reserved source has duplicate or out-of-period rows")
        daily[key,day]=row
    actuals={}
    for row in forecast["rows"]:
        window=_window(row)
        values=[]
        available=[]
        for i in range(window.horizon_days):
            day=window.start+timedelta(days=i)
            r=daily.get((window.key,day))
            if (not r or r.get("complete_daily_sales") is not True or r.get("target_quantity") is None
                    or not (r.get("completeness_evidence_refs") or p.get("completeness_evidence_refs"))
                    or not r.get("target_available_date")):
                break
            a=date.fromisoformat(r["target_available_date"])
            if a < day or a > observed_through or finite(r["target_quantity"]) < 0:
                break
            values.append(float(r["target_quantity"]))
            available.append(a)
        if len(values)==window.horizon_days and window.end <= observed_through:
            actuals[window]=Example(window,(),sum(values),max(available))
    payload=reserved_actuals_payload(actuals)
    payload["source_ref"]=reserved_unseen_data_ref
    provenance="mock" if any(r["provenance"]=="mock" for r in (bundle_ref,reserved_unseen_data_ref)) else "derived"
    targets_ref=store.put_bytes(artifact_id,1,provenance,canonical(payload))
    return {"actuals":actuals,"reserved_targets_ref":targets_ref,"reserved_unseen_data_ref":reserved_unseen_data_ref}


def scope_keys(raw_bytes):
    """Read separately frozen development eligibility keys for DSC-29/30."""
    p=json.loads(raw_bytes)
    if p.get("format") != "dsc28-forecast-scope-v1" or not p.get("binding") or not p.get("run_id"):
        raise ModelingError("unsupported/unbound frozen development scope")
    keys=p["keys"]
    if (not keys or any(set(k)!={"source_namespace","product_id","store_id"} or not all(isinstance(v,str) and v for v in k.values()) for k in keys)
            or len({digest(k) for k in keys})!=len(keys)):
        raise ModelingError("scope must contain exact unique development eligibility keys")
    return keys
