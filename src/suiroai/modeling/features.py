"""Bounded LLM feature proposals over released development summaries only.

This module never opens raw files or fits transforms. The caller must establish
that summary bytes were computed from the permitted preparation partition in the
supported host. Digests bind those bytes; date metadata cannot prove their origin.
The private summary format deliberately excludes arbitrary prose, paths and raw
rows. Shared feature definitions are validated unchanged against DSC-24's schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
import re
import time
from typing import Callable, Sequence

from suiroai.contracts import digest, record_ref

from .core import (CUTOFF, ModelingError, bound_payload, canonical,
                   checked_definition, finite, require_parent, utc_time)
from .metrics import compare_values, metric_value

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_STATS = {"row_count", "series_count", "observed_day_count", "missing_day_count",
          "null_count", "minimum", "maximum", "mean", "median", "zero_count",
          "mae", "bias", "rmse", "feature_count"}
_CALENDAR = {"year", "month", "quarter", "day_of_week", "day_of_year",
             "week_of_year", "is_weekend", "month_sin", "month_cos",
             "weekday_sin", "weekday_cos"}
_IDENTITY_FIELDS = {"Product_ID", "Store_ID", "origin"}
_FORBIDDEN_FIELDS = {"target_quantity", "Quantity", "Inventory_Level",
                     "Delivery_Days", "Order_Status", "Return_Status"}


def _copy(value):
    try:
        return json.loads(canonical(value))
    except (ValueError, TypeError) as exc:
        raise ModelingError("feature evidence must be finite canonical JSON") from exc


def _day(value, label):
    try:
        result = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ModelingError(f"invalid {label} calendar date") from exc
    if result.isoformat() != value:
        raise ModelingError(f"{label} requires an ISO calendar date")
    return result


def _fields(values):
    if not isinstance(values, (list, tuple)) or not values or len(values) > 32:
        raise ModelingError("explicit bounded initial feature fields required")
    if (any(not isinstance(v, str) or not _IDENTIFIER.fullmatch(v) for v in values)
            or len(set(values)) != len(values)
            or set(values) & (_IDENTITY_FIELDS | _FORBIDDEN_FIELDS)):
        raise ModelingError("initial arithmetic fields must be distinct safe numeric feature names")
    return tuple(values)


@dataclass(frozen=True)
class DevelopmentArtifact:
    """Released summary bytes plus caller-verified source chronology metadata.

    No ``verified=True`` flag substitutes for checking payload bytes. The caller
    independently checks genuine preparation/source lineage and supported-host
    access before releasing these summaries. Construction checks bytes and shape.
    """

    ref: dict
    payload: dict
    max_target_date: date

    def __post_init__(self):
        checked_definition("artifact_ref", self.ref)
        if type(self.max_target_date) is not date or self.max_target_date > CUTOFF:
            raise ModelingError("LLM context must end by November 30, 2025")
        if digest(self.payload) != self.ref["sha256"]:
            raise ModelingError("released development summary digest mismatch")
        _validate_summary(self.payload, self.max_target_date)


def _validate_summary(payload, max_target_date):
    required = {"format", "binding", "run_id", "source_namespace",
                "development_end", "summary_type", "feature_fields", "statistics"}
    if (not isinstance(payload, dict) or not required <= set(payload)
            or set(payload) - required - {"task_goal", "target_policy"}):
        raise ModelingError("only structured released development summaries may reach the LLM")
    if payload["format"] != "dsc28-development-summary-v1":
        raise ModelingError("unsupported development summary format")
    checked_definition("approved_binding", payload["binding"])
    if (not isinstance(payload["run_id"], str) or not payload["run_id"]
            or payload["source_namespace"] != payload["binding"]["task_id"]):
        raise ModelingError("development summary identity is not task bound")
    if _day(payload["development_end"], "development end") != max_target_date:
        raise ModelingError("development summary chronology disagrees with released metadata")
    if not isinstance(payload["summary_type"], str) or payload["summary_type"] not in {"task_context", "eda", "development_errors", "initial_features"}:
        raise ModelingError("unsupported development summary type")
    fields = _fields(payload["feature_fields"])
    if "task_goal" in payload and payload["task_goal"] != "retail_restocking_forecast":
        raise ModelingError("unsupported task goal")
    if "target_policy" in payload and payload["target_policy"] != "positive_completed_gross_units":
        raise ModelingError("unsupported target policy")
    statistics = payload["statistics"]
    if not isinstance(statistics, list) or len(statistics) > 256:
        raise ModelingError("bounded development statistics required")
    if payload["summary_type"] == "task_context" and not {"task_goal", "target_policy"} <= set(payload):
        raise ModelingError("task context must state the bounded goal and prepared target meaning")
    if payload["summary_type"] in {"eda", "development_errors"} and not statistics:
        raise ModelingError("EDA and development errors require measured structured summaries")
    for stat in statistics:
        if (not isinstance(stat, dict)
                or not {"name", "value", "period_start", "period_end"} <= set(stat)
                or set(stat) - {"name", "value", "period_start", "period_end", "feature", "Product_ID", "Store_ID"}):
            raise ModelingError("only named structured development statistics are allowed")
        if not isinstance(stat["name"], str) or stat["name"] not in _STATS:
            raise ModelingError("unsupported development statistic")
        finite(stat["value"], "development statistic")
        if not _day(stat["period_start"], "statistic start") <= _day(stat["period_end"], "statistic end") <= max_target_date:
            raise ModelingError("development statistic includes an invalid/future period")
        if "feature" in stat and stat["feature"] not in fields:
            raise ModelingError("statistic feature is not an explicit initial feature")
        for identity in ("Product_ID", "Store_ID"):
            if identity in stat and (not isinstance(stat[identity], str) or not _IDENTIFIER.fullmatch(stat[identity])):
                raise ModelingError("statistic identity must be a bounded source identifier")


def _spec(definition, fields, refs):
    checked_definition("feature_definition", definition)
    if not _IDENTIFIER.fullmatch(definition["feature_id"]) or definition["feature_id"] in set(fields) | _IDENTITY_FIELDS:
        raise ModelingError("additional feature identifier collides with original fields")
    if definition["minimum_lag_calendar_days"] != 0:
        raise ModelingError("outcome lags lack verified availability and are not admitted")
    allowed_refs = {digest(r) for r in refs}
    if not all(digest(ref) in allowed_refs for ref in definition["source_refs"]):
        raise ModelingError("feature refers to unreleased source artifacts")
    try:
        spec = json.loads(definition["expression"])
    except (TypeError, ValueError) as exc:
        raise ModelingError("feature expression must contain declarative JSON") from exc
    if not isinstance(spec, dict):
        raise ModelingError("feature transform must be a JSON object")
    op = spec.get("op")
    if op == "calendar":
        if (set(spec) != {"op", "part"} or not isinstance(spec["part"], str)
                or spec["part"] not in _CALENDAR):
            raise ModelingError("unsupported calendar transform")
    elif isinstance(op, str) and op in {"add", "multiply", "ratio"}:
        expected = {"op", "fields"} | ({"zero_division"} if op == "ratio" else set())
        if (set(spec) != expected or not isinstance(spec["fields"], list)
                or len(spec["fields"]) != 2
                or any(f not in fields for f in spec["fields"])
                or (op == "ratio" and spec["zero_division"] != "null")):
            raise ModelingError("arithmetic must use two released initial fields and explicit null division")
    else:
        raise ModelingError("only stateless calendar and bounded arithmetic transforms are admitted")
    return spec


def _check_initial(initial, reference, execution, preparation, parent):
    checked_definition("initial_evaluation_result", initial)
    checked_definition("artifact_ref", reference)
    if record_ref(initial) != reference:
        raise ModelingError("initial evaluation identity/bytes digest mismatch")
    if parent != initial["parent_decision"]:
        raise ModelingError("parent initial gate differs from the reviewed record")
    if (initial["binding"] != execution["binding"] or initial["run_id"] != execution["run_id"]
            or initial["execution_contract_ref"] != record_ref(execution)
            or initial["preparation_result_ref"] != record_ref(preparation)):
        raise ModelingError("initial evaluation task/run/execution/preparation binding mismatch")
    plan = initial["evaluation_plan"]
    if plan["temporal_plan"] != execution["temporal_plan"]:
        raise ModelingError("initial evaluation changed the approved temporal plan")
    primary = [m for m in plan["metric_definitions"] if m["metric_id"] == plan["primary_metric_id"]]
    if len(primary) != 1:
        raise ModelingError("initial evaluation requires one predeclared primary metric")
    baseline, candidate = initial["baseline_scores"], initial["initial_candidate"]["scores"]
    if (len({s["metric_id"] for s in baseline}) != len(baseline)
            or len({s["metric_id"] for s in candidate}) != len(candidate)
            or {s["metric_id"] for s in baseline} != {s["metric_id"] for s in candidate}):
        raise ModelingError("initial comparison metric identities differ")
    for score in baseline:
        other = next(s for s in candidate if s["metric_id"] == score["metric_id"])
        if {k: v for k, v in score.items() if k != "value"} != {k: v for k, v in other.items() if k != "value"}:
            raise ModelingError("initial comparison populations/origins/horizons/units differ")
        finite(score["value"], "initial baseline score")
        finite(other["value"], "initial candidate score")
        if not (_day(score["forecast_origin_start"], "score origin") <= _day(score["forecast_origin_end"], "score origin")
                < _day(score["target_end_max"], "score target") <= CUTOFF):
            raise ModelingError("initial development scores contain future/invalid chronology")
    for fold in plan["development_folds"]:
        if not (_day(fold["training_end"], "training end") <= _day(fold["forecast_origin"], "fold origin")
                < _day(fold["target_start"], "target start") <= _day(fold["target_end"], "target end") <= CUTOFF):
            raise ModelingError("initial development fold contains future/invalid chronology")
    expected = compare_values(metric_value({"scores": baseline}, primary[0]["metric_id"]),
                              metric_value({"scores": candidate}, primary[0]["metric_id"]),
                              primary[0]["direction"], primary[0]["tie_tolerance"])
    if initial["comparison"] != expected:
        raise ModelingError("initial parent branch contradicts measured scores")


def generate_feature_proposal(*, execution: dict, preparation: dict, stage_request: dict,
                              context_availability: Sequence[dict], initial_evaluation: dict,
                              initial_evaluation_ref: dict, parent_decision: dict,
                              artifacts: Sequence[DevelopmentArtifact],
                              initial_feature_fields: Sequence[str],
                              llm: Callable[[str], str], model_id: str,
                              generated_at: str, provenance: str = "derived") -> dict:
    """Call the injected LLM once; return definitions and immutable call evidence.

    The caller persists prompt and response and uses their stored artifact refs
    to construct the shared ``llm_generation_provenance``. This private result
    neither authorizes a parent transition nor claims live integration acceptance.
    """
    checked_definition("execution_contract", execution)
    checked_definition("preparation_result", preparation)
    checked_definition("stage_request", stage_request)
    require_parent(preparation["parent_decision"], "preparation")
    require_parent(parent_decision, "initial_baseline_evaluation")
    require_parent(stage_request["parent_authorization"], "llm_features")
    _check_initial(initial_evaluation, initial_evaluation_ref, execution, preparation, parent_decision)
    if (preparation["binding"] != execution["binding"] or preparation["run_id"] != execution["run_id"]
            or preparation["execution_contract_ref"] != record_ref(execution)):
        raise ModelingError("preparation task/run/execution binding mismatch")
    if (stage_request["stage"] != "llm_features"
            or stage_request["binding"] != execution["binding"]
            or stage_request["run_id"] != execution["run_id"]
            or stage_request["execution_contract_ref"] != record_ref(execution)):
        raise ModelingError("feature stage request does not bind the current execution")
    for required in (initial_evaluation_ref, record_ref(preparation)):
        if required not in stage_request["released_input_refs"]:
            raise ModelingError("feature stage request did not release the preparation/initial gate")
    if "materialize_features" not in execution["allowed_actions"]:
        raise ModelingError("execution contract does not permit additional features")
    if provenance not in {"derived", "mock"} or not isinstance(model_id, str) or not model_id.strip():
        raise ModelingError("explicit LLM model and real/mock provenance required")
    if (provenance == "derived" and (execution["provenance"] == "mock"
                                    or stage_request["provenance"] == "mock"
                                    or initial_evaluation_ref["provenance"] == "mock"
                                    or any(a.ref["provenance"] == "mock" for a in artifacts))):
        raise ModelingError("mock context cannot become real LLM evidence")
    generated = utc_time(generated_at)
    if generated < utc_time(parent_decision["decided_at"]):
        raise ModelingError("feature generation cannot precede the reviewed initial gate")
    if not utc_time(stage_request["issued_at"]) <= generated <= utc_time(stage_request["deadline"]):
        raise ModelingError("feature generation is outside the parent-issued stage window")
    remaining = stage_request["remaining_limits"]
    if remaining["max_execution_seconds"] < 1 or remaining["max_stage_attempts"] < 1:
        raise ModelingError("feature stage execution/attempt budget is exhausted")
    if stage_request["attempt"] > execution["limits"]["max_stage_attempts"]:
        raise ModelingError("feature stage attempt exceeds approved limits")
    fields = _fields(initial_feature_fields)
    prepared_ids = {d["feature_id"] for d in preparation["initial_feature_definitions"]}
    if not set(fields) <= prepared_ids:
        raise ModelingError("initial feature fields are not defined by the approved preparation result")
    if not artifacts or len(artifacts) > 8:
        raise ModelingError("bounded released development context required")
    if (len({digest(a.ref) for a in artifacts}) != len(artifacts)
            or len(context_availability) != len(artifacts)):
        raise ModelingError("released context and availability must have distinct matching identities")
    for availability in context_availability:
        checked_definition("artifact_availability", availability)
    if not {"task_context", "eda", "development_errors"} <= {a.payload.get("summary_type") for a in artifacts}:
        raise ModelingError("LLM proposal requires released task context, EDA and development errors")
    released = []
    for artifact in artifacts:
        artifact.__post_init__()  # Recheck bytes after release; mutable aliases cannot bypass hash checks.
        payload = artifact.payload
        if (artifact.ref not in stage_request["released_input_refs"]
                or artifact.ref == preparation["reserved_unseen_data_ref"]):
            raise ModelingError("summary is not released by the parent feature-stage allowlist")
        matching = [a for a in context_availability if a.get("artifact_ref") == artifact.ref]
        if len(matching) != 1:
            raise ModelingError("released summary needs unique availability evidence")
        availability = matching[0]
        if (availability["permitted_use"] != "development"
                or availability["contains_post_cutoff_rows"]
                or not _day(availability["earliest_event_date"], "context start") <= artifact.max_target_date
                or _day(availability["latest_event_date"], "context end") != artifact.max_target_date
                or _day(availability["latest_information_available_date"], "context availability") > CUTOFF):
            raise ModelingError("future/unreleased summary cannot enter feature context")
        if (payload["binding"] != execution["binding"] or payload["run_id"] != execution["run_id"]
                or tuple(payload["feature_fields"]) != fields):
            raise ModelingError("development summary binding/initial feature mismatch")
        released.append({"ref": artifact.ref, "summary": payload})
    limit = min(execution["limits"]["max_llm_feature_definitions"],
                remaining["max_llm_feature_definitions"], 32 - len(fields))
    if limit < 1:
        raise ModelingError("initial feature vector leaves no approved additional feature capacity")
    prompt = canonical({
        "purpose": "Propose additional retail demand features; original features remain the reference.",
        "constraints": {"development_cutoff": CUTOFF.isoformat(), "maximum_definitions": limit,
                        "no_outcome_lags_or_learned_transforms": True,
                        "fit_scope": "training_fold_only", "initial_numeric_fields": fields,
                        "allowed_calendar_parts": sorted(_CALENDAR),
                        "allowed_arithmetic": ["add", "multiply", "ratio"],
                        "ratio_zero_division": "null", "origin_is_only_calendar_source": True},
        "response_format": {"definitions": "Array of DSC-24 feature_definition objects; expression is JSON {op,part} for calendar or {op,fields} for add/multiply or {op,fields,zero_division:'null'} for ratio. Include meaning in name, rationale, source_refs from released summaries, origin timing and unchanged inference behavior; no new schema fields."},
        "released_development_summaries": released,
    }).decode()
    started = time.monotonic()
    response = llm(prompt)
    if time.monotonic() - started > min(remaining["max_execution_seconds"], execution["limits"]["max_execution_seconds"]):
        raise ModelingError("feature generation exhausted the bounded execution time")
    if not isinstance(response, str) or len(response.encode()) > 128_000:
        raise ModelingError("LLM response must be bounded JSON text")
    try:
        parsed = json.loads(response)
    except ValueError as exc:
        raise ModelingError("LLM response must be a JSON object") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"definitions"} or not isinstance(parsed["definitions"], list):
        raise ModelingError("LLM response must contain only definitions")
    definitions = parsed["definitions"]
    if not 1 <= len(definitions) <= limit:
        raise ModelingError("LLM feature count exceeds approved limit or is empty")
    refs = [a.ref for a in artifacts]
    for definition in definitions:
        _spec(definition, fields, refs)
    if len({d["feature_id"] for d in definitions}) != len(definitions):
        raise ModelingError("duplicate generated feature identifiers")
    return _copy(bound_payload({
        "format": "dsc28-feature-proposal-v1", "provenance": provenance,
        "initial_evaluation_ref": initial_evaluation_ref, "parent_initial_decision": parent_decision,
        "preparation_result_ref": record_ref(preparation),
        "original_feature_set_ref": preparation["initial_feature_set_ref"],
        "stage_request_ref": record_ref(stage_request),
        "context_availability": list(context_availability),
        "definitions": definitions, "initial_feature_fields": list(fields),
        "feature_sources": [{"feature_id": d["feature_id"],
                             "source_fields": json.loads(d["expression"]).get("fields", ["origin"]),
                             "meaning": d["name"], "source_refs": d["source_refs"]}
                            for d in definitions],
        "model_id": model_id, "generated_at": generated_at,
        "development_context_refs": refs, "unrestricted_raw_future_access": False,
        "prompt": prompt, "response": response,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "response_sha256": hashlib.sha256(response.encode()).hexdigest(),
        "selection_status": "proposed_only_not_earned_inclusion",
        "limitations": ["Caller must verify released summaries were derived exclusively from development bytes in the supported host; metadata and hashes alone cannot establish their historical source.",
                        "Outcome lags and learned feature transforms are excluded while availability is unknown."],
    }, execution))


def _calculate(spec, row):
    if spec["op"] == "calendar":
        origin = _day(row["origin"], "feature origin")
        part = spec["part"]
        direct = {"year": origin.year, "month": origin.month,
                  "quarter": (origin.month - 1) // 3 + 1,
                  "day_of_week": origin.weekday(), "day_of_year": origin.timetuple().tm_yday,
                  "week_of_year": origin.isocalendar().week, "is_weekend": int(origin.weekday() >= 5)}
        if part in direct:
            return direct[part]
        phase = (origin.month - 1) / 12 if part.startswith("month") else origin.weekday() / 7
        return (math.sin if part.endswith("sin") else math.cos)(2 * math.pi * phase)
    left, right = (row[f] for f in spec["fields"])
    if left is None or right is None:
        return None
    if spec["op"] == "ratio":
        return None if right == 0 else left / right
    return left + right if spec["op"] == "add" else left * right


def materialize_features(rows: Sequence[dict], definitions: Sequence[dict], *,
                         initial_feature_fields: Sequence[str], source_refs: Sequence[dict]) -> dict:
    """Pure stateless transform usable at development and frozen inference time.

    Rows have exactly Product_ID, Store_ID, origin and explicit numeric initial
    fields. They contain no targets. Original feature values and order survive.
    No interpolation, imputation, learned fitting, joining or zero filling occurs.
    """
    fields = _fields(initial_feature_fields)
    if not rows or not definitions or len(definitions) + len(fields) > 32:
        raise ModelingError("nonempty bounded feature definitions and rows required")
    definitions = _copy(list(definitions))
    specs = [_spec(d, fields, source_refs) for d in definitions]
    ids = [d["feature_id"] for d in definitions]
    if len(set(ids)) != len(ids):
        raise ModelingError("duplicate feature identifiers")
    output, seen, null_counts = [], set(), {identifier: 0 for identifier in ids}
    for original in rows:
        if not isinstance(original, dict) or set(original) != _IDENTITY_FIELDS | set(fields):
            raise ModelingError("feature row must contain exactly identity, origin and released initial fields")
        row = _copy(original)
        key = tuple(row[k] for k in ("Product_ID", "Store_ID", "origin"))
        if any(not isinstance(v, str) or not v for v in key) or key in seen:
            raise ModelingError("feature rows need unique product/store/origin alignment")
        _day(row["origin"], "feature origin")
        seen.add(key)
        for field in fields:
            if row[field] is not None:
                finite(row[field], field)
        for identifier, spec in zip(ids, specs):
            value = _calculate(spec, row)
            if value is None:
                null_counts[identifier] += 1
            else:
                finite(value, identifier)
            row[identifier] = value
        output.append(row)
    # Recalculation establishes deterministic materialization without fitting.
    if any(_calculate(spec, row) != row[identifier]
           for row in output for identifier, spec in zip(ids, specs)):
        raise ModelingError("feature reproducibility check failed")
    return {"format": "dsc28-materialized-features-v1", "rows": output,
            "definitions": definitions, "initial_feature_fields": list(fields),
            "checks": {"row_count": len(output), "identity_alignment": True,
                       "original_values_preserved": True, "calculation_rechecked": True,
                       "finite_or_explicit_null": True, "null_counts": null_counts,
                       "stateless_no_fitted_parameters": True,
                       "reproducibility_sha256": digest(output)},
            "inference_behavior": "Reuse these definitions unchanged; calendar uses forecast origin. Arithmetic propagates null and ratio by zero returns null. Any downstream imputation fits only on training folds.",
            "selection_status": "validated_calculations_not_selected",
            "parent_approval": "required_externally"}
