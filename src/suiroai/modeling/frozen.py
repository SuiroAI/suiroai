"""Frozen November 30 forecast scoring; this worker never fits or selects models.

These private byte artifacts use DSC-26's existing ArtifactStore. The parent
owns checkpoint authentication, access isolation, transitions and retry budgets.
"""
from __future__ import annotations

from datetime import date
import json

from .core import (CUTOFF, UNSEEN_END, Example, ModelingError, Prediction, Window,
                   bound_payload, canonical, checked_definition, finite,
                   require_parent, utc_time)
from .metrics import score


def _put(store, identity, payload, provenance):
    return store.put_bytes(identity, 1, provenance, canonical(payload))


def _read(store, ref):
    try:
        return json.loads(store.read_bytes(ref))
    except (TypeError, ValueError) as exc:
        raise ModelingError("invalid frozen JSON artifact") from exc


def _provenance(requested, refs=(), execution=None):
    # A fixture anywhere in the lineage makes every descendant fixture evidence.
    if requested == "mock" or (execution or {}).get("provenance") == "mock" or any(ref.get("provenance") == "mock" for ref in refs):
        return "mock"
    return requested


def _supported_rule(rule):
    populations = set()
    for gate in rule["metric_gates"]:
        finite(gate["threshold"], "acceptance threshold")
        if (gate["metric_id"] not in {"mae", "bias"} or gate["aggregation"] != "equal_series_mean"
                or gate["direction"] not in {"upper_bound", "lower_bound"} or gate["unit"] != "product_unit"):
            raise ModelingError("unsupported acceptance gate: freeze supports absolute equal-series MAE/bias product-unit bounds only")
        populations.add(gate["population_id"])
    if len(populations) != 1:
        raise ModelingError("all frozen gates must name the same scored population")


def _window(row):
    window = Window(tuple(row["key"]), date.fromisoformat(row["origin"]), row["horizon_days"])
    if row.get("target_start") != window.start.isoformat() or row.get("target_end") != window.end.isoformat():
        raise ModelingError("forecast horizon metadata disagrees with origin")
    return window


def _check(identity, passed, expected, actual, refs):
    return {"check_id": identity, "requirement_id": "DSC-28", "status": "pass" if passed else "fail",
            "expected": expected, "actual": str(actual), "evidence_refs": refs,
            "verifier": "dsc28-frozen-calculation"}


def freeze_bundle(store, *, execution, artifact_id, selected_candidate_id, model_ref,
                  feature_set_ref, preprocessing_ref, evaluation_plan_ref, acceptance_rule,
                  development_input_refs, forecast_input_refs, forecast, frozen_at,
                  minimum_coverage_fraction=1.0, provenance="derived", daily_forecast=None):
    """Persist fixed bytes and a detached shared-contract ``frozen_result``.

    ``forecast`` is an iterable of (Window, prediction), never final actuals.
    Fitted model bytes must include their fitted configuration. The producer is
    responsible for verified training/development chronology; refs are measured
    here but their claimed temporal availability requires independent evidence.
    """
    checked_definition("acceptance_rule", acceptance_rule)
    _supported_rule(acceptance_rule)
    if execution.get("kind") == "execution_contract":
        checked_definition("execution_contract", execution)
        if acceptance_rule != execution["acceptance_rule"] or "freeze" not in execution["allowed_actions"]:
            raise ModelingError("freeze changed approved acceptance rule or action permission")
    elif not any(r.get("provenance") == "mock" for r in [model_ref,feature_set_ref,preprocessing_ref,*development_input_refs]):
        raise ModelingError("real freeze requires the complete approved execution contract")
    if utc_time(acceptance_rule["declared_at"]) > utc_time(frozen_at):
        raise ModelingError("acceptance rule must be declared before freeze")
    if not artifact_id or not selected_candidate_id or not development_input_refs or not forecast_input_refs:
        raise ModelingError("freeze needs identity and complete development/forecast lineage")
    coverage = finite(minimum_coverage_fraction, "minimum coverage fraction")
    if not 0 < coverage <= 1:
        raise ModelingError("minimum coverage fraction must be in (0, 1]")
    refs = [model_ref, feature_set_ref, preprocessing_ref, evaluation_plan_ref,
            *development_input_refs, *forecast_input_refs]
    for ref in refs:
        store.read_bytes(ref)
    provenance = _provenance(provenance, refs, execution)
    rows = []
    for window, predicted in forecast:
        if not isinstance(window, Window) or window.origin != CUTOFF or window.end > UNSEEN_END:
            raise ModelingError("November 30 forecast must cover only reserved December horizons")
        value = finite(predicted, "saved forecast")
        if value < 0:
            raise ModelingError("saved gross-unit forecast cannot be negative")
        rows.append(dict(window.payload(), predicted=value))
    if not rows or len({_window(row) for row in rows}) != len(rows):
        raise ModelingError("frozen forecast population must be nonempty and unique")
    rows.sort(key=lambda row: (row["key"], row["origin"], row["horizon_days"]))
    if acceptance_rule["minimum_observation_count"] > len(rows):
        raise ModelingError("acceptance minimum exceeds frozen forecast population")
    daily_rows = list(daily_forecast) if daily_forecast is not None else None
    if daily_rows is not None:
        _validate_daily_forecast(rows, daily_rows)
    rule_ref = _put(store, artifact_id + "/acceptance-rule", acceptance_rule, provenance)
    forecast_ref = _put(store, artifact_id + "/november30-forecast", bound_payload({
        "format": "dsc28-forecast-v1", "as_of_date": CUTOFF.isoformat(), "rows": rows,
        "daily_forecast": daily_rows, "recommendation_ready": daily_rows is not None}, execution), provenance)
    frozen = {"freeze_id": artifact_id, "frozen_at": frozen_at,
              "selected_candidate_id": selected_candidate_id, "model_ref": model_ref,
              "feature_set_ref": feature_set_ref, "preprocessing_ref": preprocessing_ref,
              "evaluation_plan_ref": evaluation_plan_ref, "acceptance_rule_ref": rule_ref,
              "development_input_refs": list(development_input_refs),
              "november_30_forecast_ref": forecast_ref, "forecast_as_of_date": CUTOFF.isoformat(),
              "forecast_input_refs": list(forecast_input_refs),
              "no_reserved_outcomes_in_fit_selection_or_forecast": True}
    checked_definition("frozen_result", frozen)
    frozen_result_ref = _put(store, artifact_id + "/frozen-result", frozen, provenance)
    bundle = bound_payload({"format": "dsc28-frozen-v1", "frozen": frozen, "frozen_result_ref": frozen_result_ref,
                            "expected_observation_count": len(rows),
                            "minimum_coverage_fraction": coverage}, execution)
    ref = _put(store, artifact_id + "/bundle", bundle, provenance)
    return {"bundle_ref": ref, "frozen": frozen, "frozen_result_ref": frozen_result_ref}


def _validate_daily_forecast(totals, daily):
    from datetime import timedelta
    index = {}
    for row in daily:
        expected_fields = {"key", "date", "quantity", "quantity_unit", "as_of_date", "latest_information_available_date"}
        if set(row) != expected_fields or set(row["key"]) != {"source_namespace", "product_id", "store_id"}:
            raise ModelingError("daily forecast needs agreed trajectory fields")
        key = tuple(row["key"][field] for field in ("source_namespace", "product_id", "store_id"))
        day = date.fromisoformat(row["date"])
        quantity = finite(row["quantity"], "daily forecast")
        if (quantity < 0 or row["quantity_unit"] != "product_unit" or row["as_of_date"] != CUTOFF.isoformat()
                or date.fromisoformat(row["latest_information_available_date"]) > CUTOFF
                or not CUTOFF < day <= UNSEEN_END or (key, day) in index):
            raise ModelingError("unsafe or duplicate daily forecast trajectory")
        index[key, day] = quantity
    required = set()
    for row in totals:
        window = _window(row)
        days = [(window.key, window.start + timedelta(days=offset)) for offset in range(window.horizon_days)]
        if any(day not in index for day in days):
            raise ModelingError("daily forecast has incomplete protection horizon")
        if abs(sum(index[day] for day in days) - row["predicted"]) > 1e-9:
            raise ModelingError("daily forecast does not sum to saved aggregate prediction")
        required.update(days)
    if set(index) != required:
        raise ModelingError("daily trajectory contains unplanned dates or series")


def verify_frozen(store, bundle_ref):
    """Re-read every exact byte ref; no mutable in-memory choice is trusted."""
    bundle = _read(store, bundle_ref)
    if bundle.get("format") != "dsc28-frozen-v1":
        raise ModelingError("unsupported frozen bundle")
    frozen = bundle["frozen"]
    checked_definition("frozen_result", frozen)
    if _read(store, bundle["frozen_result_ref"]) != frozen:
        raise ModelingError("frozen result reference disagrees with bundle")
    for field in ("model_ref", "feature_set_ref", "preprocessing_ref", "evaluation_plan_ref",
                  "acceptance_rule_ref", "november_30_forecast_ref"):
        store.read_bytes(frozen[field])
    for ref in frozen["development_input_refs"] + frozen["forecast_input_refs"]:
        store.read_bytes(ref)
    rule = _read(store, frozen["acceptance_rule_ref"])
    checked_definition("acceptance_rule", rule)
    _supported_rule(rule)
    forecast = _read(store, frozen["november_30_forecast_ref"])
    if (forecast.get("format") != "dsc28-forecast-v1" or forecast.get("as_of_date") != CUTOFF.isoformat()
            or any(forecast.get(key) != bundle.get(key) for key in ("binding", "run_id", "execution_contract_sha256"))):
        raise ModelingError("forecast is not bound to this frozen execution")
    windows = [_window(row) for row in forecast["rows"]]
    if (not windows or len(set(windows)) != len(windows)
            or len(windows) != bundle["expected_observation_count"]
            or any(w.origin != CUTOFF or w.end > UNSEEN_END for w in windows)):
        raise ModelingError("frozen forecast population changed")
    if forecast.get("recommendation_ready"):
        _validate_daily_forecast(forecast["rows"], forecast["daily_forecast"])
    elif forecast.get("daily_forecast") is not None:
        raise ModelingError("daily trajectory readiness metadata disagrees")
    return bundle, rule, forecast


def reserved_actuals_payload(actuals):
    """Serialize bounded targets supplied by preparation, with availability.

    Values must be Example instances: each must represent a fully observed
    horizon, not a sum of whichever transaction dates happen to exist. Missing
    horizons stay absent and lower measured coverage.
    """
    rows = []
    for window, value in sorted(actuals.items()):
        if not isinstance(value, Example) or value.window != window:
            raise ModelingError("reserved targets need prepared Example and availability metadata")
        rows.append(dict(window.payload(), actual=value.actual,
                         available_on=value.label_available_on.isoformat()))
    return {"format": "dsc28-reserved-targets-v1", "rows": rows}


def score_frozen(store, bundle_ref, reserved_actuals, *, holdout_accessed_at,
                 observed_through, population_id, reserved_unseen_data_ref, checks=(),
                 evidence_id=None, reserved_targets_ref=None, scored_at=None):
    """Score immutable saved values, preserving missing horizons in coverage.

    The registered reserved-target artifact must contain exactly the supplied
    numerical rows. Access isolation and observed completeness are upstream
    obligations, not facts inferred from a nonempty series.
    """
    bundle, rule, forecast = verify_frozen(store, bundle_ref)
    frozen = bundle["frozen"]
    if population_id != rule["metric_gates"][0]["population_id"]:
        raise ModelingError("final scoring population differs from frozen acceptance population")
    access = utc_time(holdout_accessed_at)
    scored_at = scored_at or holdout_accessed_at
    if utc_time(scored_at) < access:
        raise ModelingError("scoring cannot precede holdout access")
    if access <= utc_time(frozen["frozen_at"]) or access <= utc_time(rule["declared_at"]):
        raise ModelingError("holdout access must follow immutable selection and rule declaration")
    if type(observed_through) is not date or observed_through > UNSEEN_END or observed_through <= CUTOFF:
        raise ModelingError("observation cutoff must be in reserved December")
    targets = reserved_actuals_payload(reserved_actuals)
    if reserved_targets_ref is not None:
        store.read_bytes(reserved_unseen_data_ref)
        targets["source_ref"] = reserved_unseen_data_ref
    if _read(store, reserved_targets_ref or reserved_unseen_data_ref) != targets:
        raise ModelingError("reserved values disagree with measured source artifact")
    predictions, excluded = [], []
    windows = {_window(row) for row in forecast["rows"]}
    if any(window not in windows for window in reserved_actuals):
        raise ModelingError("reserved scoring contains unplanned windows")
    for row in forecast["rows"]:
        window = _window(row)
        actual = reserved_actuals.get(window)
        if actual is None or window.end > observed_through or actual.label_available_on > observed_through:
            excluded.append(dict(window.payload(), reason="unavailable_fully_observed_horizon"))
            continue
        predictions.append(Prediction(window, actual.actual, row["predicted"]))
    count, expected = len(predictions), bundle["expected_observation_count"]
    fraction = count / expected
    refs = [bundle_ref, reserved_unseen_data_ref]
    checked = list(checks)
    for check in checked:
        checked_definition("check", check)
    if len({item["check_id"] for item in checked}) != len(checked):
        raise ModelingError("duplicate required validation check")
    if any(item["check_id"] in {"frozen_coverage", "fully_observed_horizons"} for item in checked):
        raise ModelingError("caller cannot replace intrinsic frozen checks")
    checked.extend([
        _check("frozen_coverage", count >= rule["minimum_observation_count"] and fraction >= bundle["minimum_coverage_fraction"],
               "predeclared minimum observation count and frozen population coverage", f"{count}/{expected} ({fraction})", refs),
        _check("fully_observed_horizons", not excluded, "every frozen forecast horizon observed", f"excluded={len(excluded)}", refs)])
    metrics = score(predictions, population_id) if predictions else {"scores": [], "per_series": [], "aggregation": "equal_series_mean"}
    gates = []
    for gate in rule["metric_gates"]:
        matches = [s for s in metrics["scores"] if s["metric_id"] == gate["metric_id"]
                   and s["population_id"] == gate["population_id"] and s["unit"] == gate["unit"]]
        if gate["aggregation"] != metrics["aggregation"]:
            raise ModelingError("acceptance aggregation differs from measured metric")
        if gate["direction"] == "minimum_improvement_over_baseline":
            raise ModelingError("frozen scorer requires predeclared absolute gates; baseline-relative gate needs frozen baseline evidence")
        value = matches[0]["value"] if len(matches) == 1 else None
        threshold = finite(gate["threshold"], "acceptance threshold")
        passed = value is not None and (value <= threshold if gate["direction"] == "upper_bound" else value >= threshold)
        gates.append({"gate": gate, "actual": value, "passed": passed})
    index = {item["check_id"]: item for item in checked}
    required_pass = all(name in index and index[name]["status"] == "pass" for name in rule["required_check_ids"])
    intrinsic_pass = index["frozen_coverage"]["status"] == "pass"
    passed = bool(predictions) and all(g["passed"] for g in gates) and required_pass and intrinsic_pass
    evidence = {"format": "dsc28-validation-evidence-v1", "bundle_ref": bundle_ref,
                "frozen_result_ref": bundle["frozen_result_ref"],
                "binding": bundle["binding"], "run_id": bundle["run_id"],
                "execution_contract_sha256": bundle["execution_contract_sha256"], "scored_at": scored_at,
                "november_30_forecast_ref": frozen["november_30_forecast_ref"],
                "acceptance_rule": rule, "reserved_unseen_data_ref": reserved_unseen_data_ref,
                "reserved_targets_ref": reserved_targets_ref,
                "holdout_accessed_at": holdout_accessed_at, "observed_through": observed_through.isoformat(),
                "scores": metrics["scores"], "per_series": metrics["per_series"], "aggregation": metrics["aggregation"],
                "checks": checked, "gate_results": gates, "excluded_horizons": excluded,
                "eligible_observation_count": count, "expected_observation_count": expected,
                "coverage_fraction": fraction, "outcome": "pass" if passed else "fail",
                "requires_parent_review": not passed and bool(predictions),
                "execution_outcome": "completed" if predictions else "execution_failed",
                "limitations": ["Forecast accuracy alone does not establish stockout, profit or inventory-cost improvement.",
                                "Prepared target completeness and availability require independent upstream evidence."]}
    provenance_refs = [bundle_ref, reserved_unseen_data_ref] + ([reserved_targets_ref] if reserved_targets_ref else [])
    provenance_refs.extend(ref for check in checked for ref in check["evidence_refs"])
    ref = _put(store, evidence_id or frozen["freeze_id"] + "/validation-evidence", evidence,
               _provenance(bundle_ref["provenance"], provenance_refs))
    return {"evidence_ref": ref, "evidence": evidence}


def finalize_validation(store, evidence_ref, *, parent_review=None, defect_rechecks=(),
                        max_defect_rechecks=0):
    """Classify evidence for DSC-10 without owning its state or permitting retry.

    A failed initial measurement always requires internal parent review. Recheck
    bytes must have been produced by ``record_defect_recheck`` below.
    """
    evidence = _read(store, evidence_ref)
    if evidence.get("format") != "dsc28-validation-evidence-v1":
        raise ModelingError("unsupported final evidence")
    verify_frozen(store, evidence["bundle_ref"])
    if (type(max_defect_rechecks) is not int or max_defect_rechecks < 0
            or len(defect_rechecks) > max_defect_rechecks or len(defect_rechecks) > 1):
        raise ModelingError("bounded defect recovery limit exceeded")
    if evidence["outcome"] == "pass":
        if defect_rechecks:
            raise ModelingError("passing initial evidence cannot trigger recovery")
        return {"outcome": "pass", "evidence_ref": evidence_ref, "parent_review": parent_review}
    if parent_review is None:
        return {"outcome": "parent_review_required", "evidence_ref": evidence_ref, "parent_review": None}
    require_parent(parent_review, "final_validation", allowed=("review", "confirmed_failure", "stop", "pass_after_recheck", "allow_defect_recheck"))
    if evidence_ref not in parent_review["evidence_refs"]:
        raise ModelingError("parent review does not bind failed measurement")
    if utc_time(parent_review["decided_at"]) < utc_time(evidence["holdout_accessed_at"]):
        raise ModelingError("parent review precedes the failed measurement")
    if evidence.get("execution_outcome") == "execution_failed":
        return {"outcome": "execution_failed", "evidence_ref": evidence_ref, "parent_review": parent_review}
    latest = evidence
    for index, recheck_ref in enumerate(defect_rechecks, 1):
        recheck = _read(store, recheck_ref)
        if recheck.get("format") != "dsc28-defect-recheck-v1":
            raise ModelingError("unsupported defect recheck evidence")
        if recheck.get("original_evidence_ref") != evidence_ref or recheck.get("attempt") != index:
            raise ModelingError("recheck evidence changed original failed result or attempt order")
        require_parent(recheck["parent_authorization"], "final_validation", allowed=("allow_defect_recheck",))
        if evidence_ref not in recheck["parent_authorization"]["evidence_refs"]:
            raise ModelingError("defect authorization does not bind original failure")
        if recheck["november_30_forecast_ref"] != evidence["november_30_forecast_ref"]:
            raise ModelingError("recheck changed saved November 30 forecast")
        for ref in recheck["defect_evidence_refs"] + recheck["correction_refs"]:
            store.read_bytes(ref)
        if utc_time(recheck["parent_authorization"]["decided_at"]) >= utc_time(recheck["recheck_started_at"]):
            raise ModelingError("recheck preceded its parent authorization")
        if recheck["outcome"] == "execution_failure":
            return {"outcome": "execution_failed", "evidence_ref": recheck_ref, "parent_review": parent_review}
        latest = _read(store, recheck["corrected_evidence_ref"])
        _same_frozen_evidence(evidence, latest)
        if utc_time(latest["scored_at"]) < utc_time(recheck["recheck_started_at"]):
            raise ModelingError("corrected scoring preceded recheck start")
        if recheck["outcome"] != latest["outcome"]:
            raise ModelingError("recheck outcome disagrees with measured correction")
    if defect_rechecks and latest["outcome"] == "pass":
        if parent_review["decision"] != "pass_after_recheck" or defect_rechecks[-1] not in parent_review["evidence_refs"]:
            return {"outcome": "parent_review_required", "evidence_ref": defect_rechecks[-1], "parent_review": parent_review}
        return {"outcome": "pass", "evidence_ref": defect_rechecks[-1], "parent_review": parent_review}
    if parent_review["decision"] in {"review", "allow_defect_recheck"} and not defect_rechecks and max_defect_rechecks > 0:
        return {"outcome": "parent_review_required", "evidence_ref": evidence_ref, "parent_review": parent_review}
    return {"outcome": "validation_failed", "evidence_ref": defect_rechecks[-1] if defect_rechecks else evidence_ref,
            "parent_review": parent_review}


def record_defect_recheck(store, original_evidence_ref, corrected_evidence_ref, *, attempt,
                          max_defect_rechecks, defect_description, defect_evidence_refs,
                          correction_refs, parent_authorization, artifact_id, recheck_started_at):
    """Accept only demonstrated scoring/calculation correction under fixed choice.

    No callable fitting/scoring hook is accepted: the caller supplies measured
    corrected evidence under exactly the same frozen model, rule and forecast.
    """
    if type(attempt) is not int or attempt != 1 or attempt > max_defect_rechecks:
        raise ModelingError("defect recheck budget exhausted")
    require_parent(parent_authorization, "final_validation", allowed=("allow_defect_recheck",))
    if original_evidence_ref not in parent_authorization["evidence_refs"] or not defect_description or not defect_evidence_refs or not correction_refs:
        raise ModelingError("bounded correction needs identified defect, evidence and parent authorization")
    original = _read(store, original_evidence_ref)
    corrected = _read(store, corrected_evidence_ref)
    if original["outcome"] != "fail":
        raise ModelingError("only failed measurement can receive defect correction")
    _same_frozen_evidence(original, corrected)
    if (utc_time(parent_authorization["decided_at"]) >= utc_time(recheck_started_at)
            or utc_time(recheck_started_at) > utc_time(corrected["scored_at"])
            or utc_time(parent_authorization["decided_at"]) < utc_time(original["scored_at"])):
        raise ModelingError("defect recheck must follow parent authorization and precede correction measurement")
    verify_frozen(store, original["bundle_ref"])
    for ref in [*defect_evidence_refs, *correction_refs]:
        store.read_bytes(ref)
    payload = {"format": "dsc28-defect-recheck-v1", "original_evidence_ref": original_evidence_ref,
               "corrected_evidence_ref": corrected_evidence_ref, "attempt": attempt, "recheck_started_at": recheck_started_at,
               "defect_description": defect_description, "defect_evidence_refs": list(defect_evidence_refs),
               "correction_refs": list(correction_refs), "parent_authorization": parent_authorization,
               "model_selection_unchanged": True, "november_30_forecast_ref": original["november_30_forecast_ref"],
               "outcome": corrected["outcome"]}
    payload.update({key: original[key] for key in ("binding", "run_id", "execution_contract_sha256")})
    return _put(store, artifact_id, payload, _provenance(original_evidence_ref["provenance"],
                [original_evidence_ref, *defect_evidence_refs, *correction_refs, *parent_authorization["evidence_refs"]]))


def _same_frozen_evidence(original, corrected):
    if corrected.get("format") != "dsc28-validation-evidence-v1":
        raise ModelingError("unsupported corrected measurement")
    for field in ("bundle_ref", "november_30_forecast_ref", "acceptance_rule", "reserved_unseen_data_ref",
                  "holdout_accessed_at", "observed_through", "expected_observation_count", "reserved_targets_ref",
                  "binding", "run_id", "execution_contract_sha256", "frozen_result_ref"):
        if corrected.get(field) != original.get(field):
            raise ModelingError("defect recheck changed frozen selection, rule, source or chronology")


def record_failed_defect_recheck(store, original_evidence_ref, *, attempt, max_defect_rechecks,
                                 defect_description, defect_evidence_refs, correction_refs,
                                 parent_authorization, artifact_id, error_code, failure_evidence_refs, recheck_started_at):
    """Preserve an operationally failed correction with no fabricated scores."""
    if type(attempt) is not int or attempt != 1 or attempt > max_defect_rechecks:
        raise ModelingError("defect recheck budget exhausted")
    require_parent(parent_authorization, "final_validation", allowed=("allow_defect_recheck",))
    original = _read(store, original_evidence_ref)
    if (original.get("outcome") != "fail" or original_evidence_ref not in parent_authorization["evidence_refs"]
            or not defect_description or not defect_evidence_refs or not correction_refs or not failure_evidence_refs):
        raise ModelingError("failed correction needs bound defect and operational evidence")
    if (utc_time(parent_authorization["decided_at"]) >= utc_time(recheck_started_at)
            or utc_time(parent_authorization["decided_at"]) < utc_time(original["scored_at"])):
        raise ModelingError("failed correction must follow parent authorization")
    if error_code not in {"plugin_unavailable", "unsupported_integration", "inaccessible_input", "invalid_code", "timeout",
                          "cancelled", "budget_exhausted", "runtime_error", "integrity_error"}:
        raise ModelingError("unsupported operational failure code")
    verify_frozen(store, original["bundle_ref"])
    for ref in [*defect_evidence_refs, *correction_refs, *failure_evidence_refs]:
        store.read_bytes(ref)
    payload = {"format": "dsc28-defect-recheck-v1", "original_evidence_ref": original_evidence_ref,
               "corrected_evidence_ref": None, "attempt": attempt, "recheck_started_at": recheck_started_at, "defect_description": defect_description,
               "defect_evidence_refs": list(defect_evidence_refs), "correction_refs": list(correction_refs),
               "parent_authorization": parent_authorization, "model_selection_unchanged": True,
               "november_30_forecast_ref": original["november_30_forecast_ref"], "scores": [],
               "outcome": "execution_failure", "error_code": error_code, "failure_evidence_refs": list(failure_evidence_refs)}
    payload.update({key: original[key] for key in ("binding", "run_id", "execution_contract_sha256")})
    return _put(store, artifact_id, payload, _provenance(original_evidence_ref["provenance"],
                [original_evidence_ref, *defect_evidence_refs, *correction_refs, *failure_evidence_refs, *parent_authorization["evidence_refs"]]))


def shared_defect_recheck(store, recheck_ref):
    """Project private recovery evidence into DSC-24's exact nested definition.

    The returned object does not grant recovery permission or approve delivery;
    parent orchestration still owns bounded authorization and terminal review.
    """
    private = _read(store, recheck_ref)
    if private.get("format") != "dsc28-defect-recheck-v1":
        raise ModelingError("unsupported defect recheck evidence")
    original = _read(store, private["original_evidence_ref"])
    require_parent(private["parent_authorization"], "final_validation", allowed=("allow_defect_recheck",))
    if (private["original_evidence_ref"] not in private["parent_authorization"]["evidence_refs"]
            or private["november_30_forecast_ref"] != original["november_30_forecast_ref"]
            or private["model_selection_unchanged"] is not True or private["attempt"] != 1
            or utc_time(private["parent_authorization"]["decided_at"]) >= utc_time(private["recheck_started_at"])):
        raise ModelingError("shared recheck projection lost parent, chronology or frozen binding")
    verify_frozen(store, original["bundle_ref"])
    for ref in private["defect_evidence_refs"] + private["correction_refs"]:
        store.read_bytes(ref)
    if private["outcome"] == "execution_failure":
        for ref in private["failure_evidence_refs"]:
            store.read_bytes(ref)
        scores = []
        checks = [_check("defect_recheck_execution", False, "bounded scoring correction completes",
                         private["error_code"], private["failure_evidence_refs"])]
    else:
        corrected = _read(store, private["corrected_evidence_ref"])
        _same_frozen_evidence(original, corrected)
        if private["outcome"] != corrected["outcome"]:
            raise ModelingError("private recheck outcome contradicts measured evidence")
        scores, checks = corrected["scores"], corrected["checks"]
    shared = {"attempt": private["attempt"], "defect_description": private["defect_description"],
              "defect_evidence_refs": private["defect_evidence_refs"], "correction_refs": private["correction_refs"],
              "parent_authorization": private["parent_authorization"], "model_selection_unchanged": True,
              "november_30_forecast_ref": private["november_30_forecast_ref"], "scores": scores,
              "checks": checks, "outcome": private["outcome"]}
    checked_definition("defect_recheck", shared)
    return shared
