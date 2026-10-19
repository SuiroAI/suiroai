"""DSC-24 draft interface validation. Does not execute an analytical task.

Validate individual records and linked handoffs against the retail schema
and semantic rules for approvals, evidence, chronology, and terminal outcomes.
Provide canonical reference digests and a command to check example bundles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
VERSION = "0.1.0-draft.3"
ENVELOPE = {
    "kind", "schema_version", "artifact_id", "artifact_version", "provenance",
    "binding", "input_binding", "run_id",
}


def digest(value: Any) -> str:
    """Hash canonical contract JSON; raw source bytes use their own byte hashes."""
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def proposal_digest(proposal: dict) -> str:
    return digest({k: v for k, v in proposal.items() if k not in ENVELOPE})


def input_digest(submission: dict) -> str:
    return digest({"original_request": submission["original_request"],
                   "files": submission["files"]})


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


@lru_cache(maxsize=1)
def schema_validator() -> Draft202012Validator:
    schema = json.loads((ROOT / "schema/retail-contract.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_record(record: dict) -> list[str]:
    if not isinstance(record, dict):
        return ["record must be an object"]
    validator = schema_validator()
    kind = record.get("kind")
    if kind in validator.schema["$defs"]:
        schema = {"$ref": f"#/$defs/{kind}", "$defs": validator.schema["$defs"]}
        validator = validator.evolve(schema=schema)
    return [f"{'.'.join(map(str, e.absolute_path)) or '$'}: {e.message}"
            for e in validator.iter_errors(record)]


def ref_key(ref: dict) -> tuple:
    return ref["artifact_id"], ref["version"], ref["sha256"]


def record_ref(record: dict) -> dict:
    return {"artifact_id": record["artifact_id"],
            "version": record["artifact_version"], "sha256": digest(record),
            "provenance": record["provenance"]}


def validate_handoff(records: list[dict], external_refs: list[dict]) -> list[str]:
    """Check a self-contained handoff, without choosing parent transitions.

    External references must already have been checked by the caller against the
    artifact store. This function checks graph consistency, not remote bytes,
    execution authenticity, model reliability, or caller identity.
    """
    errors: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            errors.append("record must be an object")
            continue
        errors.extend(f"{record.get('artifact_id', '?')}: {e}"
                      for e in validate_record(record))
    if errors:
        return errors
    for record in records:
        for obj in walk(record):
            for value in obj.values():
                if isinstance(value, float) and not math.isfinite(value):
                    errors.append("nonfinite numbers are not valid measured evidence")
            if {"check_id", "requirement_id", "status", "expected", "actual", "evidence_refs", "verifier"} == set(obj):
                if obj["status"] in {"pass", "fail"} and (obj["actual"] is None or not obj["evidence_refs"]):
                    errors.append("measured checks require actual values and bound evidence")
            for key, values in obj.items():
                if isinstance(values, list) and values and all(isinstance(v, dict) for v in values):
                    for fields in (("metric_id", "population_id", "unit"), ("check_id",)):
                        if all(all(f in v for f in fields) for v in values):
                            ids = [tuple(v[f] for f in fields) for v in values]
                            if len(ids) != len(set(ids)):
                                errors.append(f"duplicate {key} identities")
            if {"metric_id", "value", "unit", "population_id", "observation_count", "forecast_origin_start", "forecast_origin_end", "target_end_max"} == set(obj):
                if not obj["forecast_origin_start"] <= obj["forecast_origin_end"] < obj["target_end_max"]:
                    errors.append("score origin/horizon chronology invalid")
    if errors:
        return errors
    internal = {ref_key(record_ref(r)): r for r in records}
    known_refs = [record_ref(r) for r in records] + external_refs
    catalog = {ref_key(r): r for r in known_refs}
    known = set(catalog)
    immutable = {}
    for ref in known_refs:
        identity = ref["artifact_id"], ref["version"]
        if identity in immutable and immutable[identity] != ref:
            errors.append("conflicting hash/provenance for immutable artifact identity/version")
        immutable[identity] = ref
    identities = [(r["artifact_id"], r["artifact_version"]) for r in records]
    if len(identities) != len(set(identities)):
        errors.append("duplicate artifact identity/version")
    for record in records:
        for obj in walk(record):
            if set(obj) == {"artifact_id", "version", "sha256", "provenance"}:
                if ref_key(obj) not in known:
                    errors.append(f"{record['artifact_id']}: unresolved or altered artifact reference {obj['artifact_id']}")
                if obj["provenance"] == "mock" and record["provenance"] != "mock":
                    errors.append("mock artifact cannot be promoted to real downstream evidence")
                target = catalog.get(ref_key(obj))
                if target and obj["provenance"] != target["provenance"]:
                    errors.append("reference provenance differs from bound artifact")
    by_kind: dict[str, list[dict]] = {}
    for r in records:
        by_kind.setdefault(r["kind"], []).append(r)

    def one(kind: str) -> dict | None:
        values = by_kind.get(kind, [])
        if kind == "quantity_result":
            return max(values, key=lambda r: r["artifact_version"]) if values else None
        if len(values) > 1:
            errors.append(f"one current {kind} per handoff; retain history separately")
        return values[-1] if values else None

    submission, proposal, approval, execution = [one(k) for k in
        ("submission", "task_proposal", "task_approval", "execution_contract")]
    if submission and submission["binding"]["input_digest"] != input_digest(submission):
        errors.append("submission input digest differs from raw request/file snapshot")
    if proposal:
        if not submission or proposal["submission_ref"] != record_ref(submission):
            errors.append("proposal must reference the exact supplied submission")
        if proposal["binding"]["proposal_digest"] != proposal_digest(proposal):
            errors.append("proposal business payload digest mismatch")
        if submission:
            for field in ("task_id", "task_version", "input_version", "input_digest"):
                if proposal["binding"][field] != submission["binding"][field]:
                    errors.append(f"proposal/submission {field} mismatch")
            accessible = {(f["file_id"], f["sha256"]) for f in submission["files"]
                          if f["access"] == "accessible"}
            for ref in proposal["source_refs"]:
                if (ref["artifact_id"], ref["sha256"]) not in accessible:
                    errors.append("proposal source not in actual accessible submission")
    if approval:
        if not proposal or approval["proposal_ref"] != record_ref(proposal):
            errors.append("approval does not refer to the current exact proposal")
    for record in records:
        if proposal and record["kind"] != "submission" and record["binding"] != proposal["binding"]:
            errors.append(f"{record['artifact_id']}: task/input/proposal binding mismatch")
        if execution and record["kind"] not in {"submission", "task_proposal", "task_approval"}:
            if record["run_id"] != execution["run_id"]:
                errors.append(f"{record['artifact_id']}: run binding mismatch")
        if record["kind"] not in {"submission", "task_proposal", "task_approval"} and not execution:
            errors.append("execution-derived record requires its approved execution contract")
    edge_kinds = {
        "execution_contract_ref": "execution_contract", "preparation_result_ref": "preparation_result",
        "initial_evaluation_ref": "initial_evaluation_result", "feature_proposal_ref": "feature_proposal",
        "llm_feature_result_ref": "feature_result", "evaluation_result_ref": "evaluation_result",
    }
    for record in records:
        for field, kind in edge_kinds.items():
            if field in record:
                target = by_kind.get(kind, [])
                if len(target) != 1 or record[field] != record_ref(target[0]):
                    errors.append(f"{record['artifact_id']}: {field} must reference current {kind}")
    if execution:
        if not approval or approval["decision"] != "approved":
            errors.append("execution requires explicit approved decision; silence/rejection cannot execute")
        elif execution["approval_ref"] != record_ref(approval):
            errors.append("execution approval reference mismatch")
        if not proposal or execution["proposal_ref"] != record_ref(proposal):
            errors.append("execution proposal reference mismatch")
        elif proposal["readiness"] != "ready":
            errors.append("execution cannot proceed with material input gaps")
        else:
            for source, target in (("source_refs", "source_refs"),
                                   ("temporal_plan", "temporal_plan"), ("assumptions", "source_assumptions")):
                if execution[target] != proposal[source]:
                    errors.append(f"execution changed approved {source}")
            if proposal["target_policy"].get("status") != "pending":
                if execution["target_policy"] != proposal["target_policy"]:
                    errors.append("execution changed approved target policy")
            # A pending statistical rule can be declared internally before the
            # freeze; a concrete approved rule cannot be changed silently.
            if proposal["acceptance_rule"].get("status") != "pending":
                if execution["acceptance_rule"] != proposal["acceptance_rule"]:
                    errors.append("execution changed approved acceptance rule")
            if any(g["material"] and "execution" in g["blocks"] for g in proposal["gaps"]):
                errors.append("execution has unresolved material blocking gaps")
        if execution["inbound_ledger_policy"] == "complete_synthetic_ledger_absence_is_zero":
            if not execution["synthetic_operational_source_refs"]:
                errors.append("complete-ledger zero rule requires explicit synthetic source scope")

    preparation = one("preparation_result")
    availability = {}
    for record in records:
        for a in record.get("availability", []):
            prior = availability.get(ref_key(a["artifact_ref"]))
            if prior is not None and prior != a:
                errors.append("conflicting availability declarations for immutable artifact")
            availability[ref_key(a["artifact_ref"])] = a
            if a["permitted_use"] == "development" and (
                a["contains_post_cutoff_rows"] or a["latest_event_date"] > "2025-11-30"
                or a["latest_information_available_date"] > "2025-11-30"):
                errors.append("development artifact contains future rows/information")

    def development_only(refs: list[dict], label: str):
        for ref in refs:
            metadata = availability.get(ref_key(ref))
            if not metadata or metadata["permitted_use"] != "development":
                errors.append(f"{label}: development input is not in verified development availability")

    if preparation:
        development_only(preparation["development_context_allowlist"], "preparation allowlist")
        development_only([preparation["prepared_development_data_ref"], preparation["initial_feature_set_ref"]], "prepared artifacts")
        reserved = availability.get(ref_key(preparation["reserved_unseen_data_ref"]))
        if not reserved or reserved["permitted_use"] != "reserved_unseen_evaluation":
            errors.append("reserved unseen data requires distinct availability metadata")
        if execution and execution["target_policy"].get("status") != "pending" and preparation["target_policy"] != execution["target_policy"]:
            errors.append("preparation changed the approved target policy")
        if execution and execution["target_policy"].get("status") == "pending" and not preparation["target_policy"]["policy_evidence_refs"]:
            errors.append("pending analytical target resolution requires versioned preparation evidence")
        policy = preparation["target_policy"]
        if policy["missing_date_treatment"] == "zero_under_disclosed_synthetic_assumption":
            zero_ref = policy["zero_assumption_ref"]
            if not execution or not any(a["classification"] == "synthetic_assumption" and zero_ref in a["source_refs"] for a in execution["source_assumptions"]):
                errors.append("synthetic missing-date zero treatment requires approved disclosed assumption")
    for record in records:
        for definition in record.get("initial_feature_definitions", []) + record.get("definitions", []):
            development_only(definition["source_refs"], "feature source dependencies")
    initial = one("initial_evaluation_result")
    feature_proposal = one("feature_proposal")
    if execution and feature_proposal and len(feature_proposal["definitions"]) > execution["limits"]["max_llm_feature_definitions"]:
        errors.append("generated feature definitions exceed declared limit")
    if feature_proposal:
        if not initial or feature_proposal["initial_evaluation_ref"] != record_ref(initial):
            errors.append("LLM features require the initial baseline checkpoint")
        elif initial["parent_decision"]["decision"] != "proceed":
            errors.append("LLM features require parent proceed after initial checkpoint")
        elif initial["comparison"] != "better" and not initial["parent_decision"]["evidence_refs"]:
            errors.append("equal/worse initial result requires evidenced bounded parent review before features")
        development_only(feature_proposal["generation"]["development_context_refs"], "feature context")
    if initial and preparation and preparation["parent_decision"]["decision"] != "proceed":
        errors.append("initial evaluation requires parent preparation authorization")
    feature_result = one("feature_result")
    if feature_result and (not feature_proposal or feature_result["definitions"] != feature_proposal["definitions"]):
        errors.append("materialized features differ from proposed definitions")
    evaluations = by_kind.get("evaluation_result", [])
    for result in by_kind.get("initial_evaluation_result", []) + evaluations:
        for fold in result["evaluation_plan"]["development_folds"]:
            if not (fold["training_end"] <= fold["forecast_origin"] < fold["target_start"] <= fold["target_end"] <= "2025-11-30"):
                errors.append("development target horizon or training chronology crosses cutoff")
        baseline = result["baseline_scores"]
        candidates = result.get("candidates", [result.get("initial_candidate")])
        if len({c["candidate_id"] for c in candidates}) != len(candidates):
            errors.append("candidate identities must be unique")
        metrics = result["evaluation_plan"]["metric_definitions"]
        if len({m["metric_id"] for m in metrics}) != len(metrics):
            errors.append("metric definitions must be unique")
        for candidate in candidates:
            signature = lambda score: {k: v for k, v in score.items() if k != "value"}
            if [signature(s) for s in candidate["scores"]] != [signature(s) for s in baseline]:
                errors.append("baseline/candidates must share metric, origins, horizons and population")
        if execution and len(candidates) > execution["limits"]["max_candidates"]:
            errors.append("candidate shortlist exceeds declared limit")
        if any(s["target_end_max"] > "2025-11-30" for s in baseline):
            errors.append("development scores contain future targets")
    if initial:
        plan = initial["evaluation_plan"]
        primary = next((m for m in plan["metric_definitions"] if m["metric_id"] == plan["primary_metric_id"]), None)
        baseline_score = next((s for s in initial["baseline_scores"] if s["metric_id"] == plan["primary_metric_id"]), None)
        initial_score = next((s for s in initial["initial_candidate"]["scores"] if s["metric_id"] == plan["primary_metric_id"]), None)
        if not primary or not baseline_score or not initial_score:
            errors.append("initial comparison lacks declared primary metric scores")
        else:
            improvement = baseline_score["value"] - initial_score["value"]
            if primary["direction"] == "higher_is_better":
                improvement *= -1
            comparison = "equal" if abs(improvement) <= primary["tie_tolerance"] else "better" if improvement > 0 else "worse"
            if initial["comparison"] != comparison:
                errors.append("initial comparison contradicts measured primary metric")
    if initial and evaluations and initial["evaluation_plan"] != evaluations[-1]["evaluation_plan"]:
        errors.append("initial and shortlist evaluations must share declared evaluation plan")
    if initial and evaluations:
        result = evaluations[-1]
        if result["baseline_id"] != initial["baseline_id"] or result["baseline_scores"] != initial["baseline_scores"]:
            errors.append("shortlist changed the initial common baseline")
        if result["initial_candidate_id"] != initial["initial_candidate"]["candidate_id"] or initial["initial_candidate"] not in result["candidates"]:
            errors.append("shortlist lost or changed measured initial candidate")
    frozen_result = evaluations[-1] if evaluations else None
    frozen = frozen_result["frozen"] if frozen_result else None
    if frozen_result:
        if feature_result and feature_result["parent_decision"]["decision"] != "proceed":
            errors.append("comparison requires parent feature authorization")
        candidates = {c["candidate_id"]: c for c in frozen_result["candidates"]}
        selected = candidates.get(frozen["selected_candidate_id"])
        if feature_result and preparation:
            options = {ref_key(c["feature_set_ref"]) for c in frozen_result["candidates"]}
            if not {ref_key(preparation["initial_feature_set_ref"]), ref_key(feature_result["materialized_feature_set_ref"])} <= options:
                errors.append("shortlist must measure original and LLM-generated feature options")
        if not selected or not selected["eligible_for_selection"]:
            errors.append("frozen candidate was not an eligible shortlisted choice")
        elif any(frozen[field] != selected[field] for field in ("model_ref", "feature_set_ref", "preprocessing_ref")):
            errors.append("frozen model/features/preprocessing differ from selected candidate")
        development_only(frozen["development_input_refs"], "frozen fit/selection")
        for ref in frozen["forecast_input_refs"]:
            metadata = availability.get(ref_key(ref))
            if not metadata or metadata["permitted_use"] not in {"development", "as_of_operations"} or metadata["latest_information_available_date"] > "2025-11-30":
                errors.append("saved forecast input contains unavailable/future information")
        if execution and frozen["acceptance_rule_ref"]["sha256"] != digest(execution["acceptance_rule"]):
            errors.append("frozen acceptance rule digest mismatch")
        if frozen["evaluation_plan_ref"]["sha256"] != digest(frozen_result["evaluation_plan"]):
            errors.append("frozen evaluation plan digest mismatch")

    final = one("final_validation_result")
    if final:
        if frozen_result and frozen_result["parent_decision"]["decision"] != "proceed":
            errors.append("holdout evaluation requires parent freeze authorization")
        if preparation and final["reserved_unseen_data_ref"] != preparation["reserved_unseen_data_ref"]:
            errors.append("final validation must use exact reserved unseen preparation artifact")
        if not frozen or final["evaluation_result_ref"] != record_ref(frozen_result):
            errors.append("final validation requires the same frozen evaluation result")
        else:
            if final["frozen_result_ref"]["sha256"] != digest(frozen):
                errors.append("final validation freeze digest mismatch")
            if final["november_30_forecast_ref"] != frozen["november_30_forecast_ref"]:
                errors.append("saved November 30 forecast changed")
            if datetime.fromisoformat(frozen["frozen_at"]) >= datetime.fromisoformat(final["holdout_accessed_at"]):
                errors.append("holdout accessed before freeze")
        if execution and final["acceptance_rule"] != execution["acceptance_rule"]:
            errors.append("final acceptance rule differs from predeclared execution rule")
        rule = final["acceptance_rule"]
        if datetime.fromisoformat(rule["declared_at"]) >= datetime.fromisoformat(final["holdout_accessed_at"]):
            errors.append("acceptance rule declared after holdout access")
        score_map = {(s["metric_id"], s["population_id"], s["unit"]): s for s in final["scores"]}
        gates_pass = True
        for gate in rule["metric_gates"]:
            score = score_map.get((gate["metric_id"], gate["population_id"], gate["unit"]))
            if not score:
                gates_pass = False
                errors.append("final metric gate missing actual score")
                continue
            if score["observation_count"] < rule["minimum_observation_count"]:
                gates_pass = False
            if not ("2025-12-01" <= score["target_end_max"] <= "2025-12-31"):
                errors.append("final score target horizon outside reserved December period")
            if gate["direction"] == "upper_bound":
                gates_pass &= score["value"] <= gate["threshold"]
            elif gate["direction"] == "lower_bound":
                gates_pass &= score["value"] >= gate["threshold"]
            else:
                # A minimum-improvement metric is explicitly scored as the
                # declared improvement, rather than silently mixing units.
                gates_pass &= score["value"] >= gate["threshold"]
        checks = {c["check_id"]: c for c in final["checks"]}
        gates_pass &= all(checks.get(k, {}).get("status") == "pass" for k in rule["required_check_ids"])
        if (final["outcome"] == "pass") != bool(gates_pass):
            errors.append("final outcome contradicts actual predeclared gates/coverage/checks")
        rechecks = final["defect_rechecks"]
        if execution and len(rechecks) > execution["limits"]["max_defect_rechecks"]:
            errors.append("defect recheck limit exhausted")
        for i, recheck in enumerate(rechecks, 1):
            if recheck["attempt"] != i or recheck["parent_authorization"]["decision"] != "allow_defect_recheck":
                errors.append("defect recheck lacks sequential bounded parent authorization")
            if frozen and recheck["november_30_forecast_ref"] != frozen["november_30_forecast_ref"]:
                errors.append("defect recheck changed the saved forecast")
            if recheck["outcome"] != "execution_failure":
                scores = {(s["metric_id"], s["population_id"], s["unit"]): s for s in recheck["scores"]}
                check_map = {c["check_id"]: c for c in recheck["checks"]}
                passes = all(check_map.get(k, {}).get("status") == "pass" for k in rule["required_check_ids"])
                for gate in rule["metric_gates"]:
                    score = scores.get((gate["metric_id"], gate["population_id"], gate["unit"]))
                    passes &= bool(score) and score["observation_count"] >= rule["minimum_observation_count"]
                    if score:
                        passes &= score["value"] <= gate["threshold"] if gate["direction"] == "upper_bound" else score["value"] >= gate["threshold"]
                if (recheck["outcome"] == "pass") != bool(passes):
                    errors.append("recheck outcome contradicts unchanged acceptance gates")
        if final["outcome"] == "fail" and final["parent_review"]["decision"] not in {"confirmed_failure", "stop", "allow_defect_recheck"}:
            errors.append("failed final evaluation lacks explicit parent review outcome")
        if rechecks:
            last = rechecks[-1]
            if last["outcome"] == "execution_failure":
                if final["outcome"] == "pass":
                    errors.append("unmeasured execution failure cannot produce passed validation")
            elif last["scores"] != final["scores"] or last["checks"] != final["checks"] or last["outcome"] != final["outcome"]:
                errors.append("final scores/checks/outcome must match last bounded recheck")
            if any(r["outcome"] == "pass" for r in rechecks[:-1]):
                errors.append("rechecks must stop after a passed frozen evaluation")

    quantities = one("quantity_result")
    report = one("report_draft")
    for result in by_kind.get("quantity_result", []) + ([report] if report else []):
        if result.get("outcome", "success") == "success":
            if not final or final["outcome"] != "pass":
                errors.append("quantities/success report require passed final validation")
            elif result["final_validation_ref"] != record_ref(final):
                errors.append("quantity/report references different final validation")
            elif not final["parent_review"] or final["parent_review"]["decision"] not in {"proceed", "pass_after_recheck"}:
                errors.append("quantities require parent authorization of passed final validation")
            if frozen and result["november_30_forecast_ref"] != frozen["november_30_forecast_ref"]:
                errors.append("quantity/report changed the saved forecast")
            if final and result["frozen_result_ref"] != final["frozen_result_ref"]:
                errors.append("quantity/report changed frozen model binding")
        for row in result["orders"]:
            if frozen and row["forecast_ref"] != frozen["november_30_forecast_ref"]:
                errors.append("quantity row uses a different saved forecast")
            need = max(0, row["forecast_quantity"] + row["safety_stock_quantity"] - row["usable_on_hand_quantity"] - row["eligible_receipt_quantity"])
            rounded = 0 if need == 0 else math.ceil(max(need, row["minimum_positive_order_quantity"]) / row["order_multiple"]) * row["order_multiple"]
            if not math.isclose(row["raw_order_need"], need) or row["rounded_order_quantity"] != rounded:
                errors.append("quantity arithmetic inconsistent (receipt summary must not be subtracted again)")
            if row["approved_order_quantity"] is not None and row["approved_order_quantity"] != rounded:
                errors.append("approved quantity differs from verified rounded quantity")
            start = date.fromisoformat(row["forecast_horizon_start"])
            end = date.fromisoformat(row["forecast_horizon_end"])
            if start != date(2025, 12, 1) or end != date(2025, 11, 30) + timedelta(days=row["supplier_lead_calendar_days"] + row["review_period_calendar_days"]):
                errors.append("quantity horizon is not lead time plus review from saved as-of")
        keys = [digest(r["key"]) for r in result["orders"]]
        if len(set(keys)) != len(keys):
            errors.append("quantity keys must be unique")
    if report and report["outcome"] == "success":
        if not quantities or report["quantity_result_ref"] != record_ref(quantities):
            errors.append("report must consume the exact approved quantity artifact")
        elif report["orders"] != quantities["orders"]:
            errors.append("report altered approved quantities")
        elif not quantities["parent_decision"] or quantities["parent_decision"]["decision"] != "proceed" or not quantities["independent_check_refs"]:
            errors.append("report requires independent numerical checks and parent approval")
        if quantities and report["exceptions"] != quantities["exceptions"]:
            errors.append("report must preserve unresolved quantity exceptions")
    for result in by_kind.get("quantity_result", []):
        if result["parent_decision"] and result["parent_decision"]["decision"] == "proceed":
            candidate_ref = result["candidate_quantity_ref"]
            candidate = internal.get(ref_key(candidate_ref)) if candidate_ref else None
            if not candidate or candidate["kind"] != "quantity_result" or candidate["artifact_id"] != result["artifact_id"] or candidate["artifact_version"] >= result["artifact_version"] or candidate["parent_decision"] is not None:
                errors.append("approved quantities require immutable earlier unapproved candidate version")
                continue
            candidate_rows = [{k: v for k, v in row.items() if k != "approved_order_quantity"} for row in candidate["orders"]]
            approved_rows = [{k: v for k, v in row.items() if k != "approved_order_quantity"} for row in result["orders"]]
            if candidate_rows != approved_rows or candidate["exceptions"] != result["exceptions"]:
                errors.append("quantity approval changed independently checked candidate content")
            if any(r["approved_order_quantity"] is not None for r in candidate["orders"]):
                errors.append("candidate quantities cannot already claim parent approval")
            if any(r["approved_order_quantity"] is None for r in result["orders"]):
                errors.append("approved quantity artifact has unapproved rows")
            if not result["independent_check_refs"]:
                errors.append("quantity approval requires typed independent evidence")
            for ref in result["independent_check_refs"]:
                evidence = internal.get(ref_key(ref))
                if not evidence or evidence["kind"] != "evidence_record" or candidate_ref not in evidence["checked_artifacts"] or evidence["check"]["status"] != "pass" or evidence["verifier_decision"] != "accepted":
                    errors.append("independent quantity evidence must check exact candidate version")
                if ref not in result["parent_decision"]["evidence_refs"]:
                    errors.append("parent quantity approval must bind independent evidence")
    for stage in by_kind.get("stage_result", []):
        request = internal.get(ref_key(stage["stage_request_ref"]))
        if not request or request["kind"] != "stage_request" or stage["stage"] != request["stage"] or stage["attempt"] != request["attempt"]:
            errors.append("stage result must bind exact stage request and attempt")
        if stage["outcome"] == "validation_failed" and (not final or final["outcome"] != "fail" or stage["final_validation_result_ref"] != record_ref(final)):
            errors.append("stage measured failure must bind failed final validation scores")
    for request in by_kind.get("stage_request", []):
        if not execution:
            continue
        if request["parent_authorization"]["decision"] != "proceed" or request["parent_authorization"]["checkpoint"] != request["stage"]:
            errors.append("stage request requires parent permission for exact stage")
        if request["attempt"] > execution["limits"]["max_stage_attempts"]:
            errors.append("stage request exceeds approved attempt limit")
        for key, value in request["remaining_limits"].items():
            if value > execution["limits"][key]:
                errors.append("stage request expands approved execution bounds")
        if request["remaining_limits"]["max_stage_attempts"] < 1 or request["remaining_limits"]["max_execution_seconds"] < 1:
            errors.append("stage cannot dispatch with exhausted attempts or time")
        if request["stage"] in {"initial_baseline_evaluation", "comparison_and_freeze"} and request["remaining_limits"]["max_candidates"] < 1:
            errors.append("model stage cannot dispatch with exhausted candidate budget")
        if request["stage"] == "llm_features" and request["remaining_limits"]["max_llm_feature_definitions"] < 1:
            errors.append("feature stage cannot dispatch with exhausted feature budget")
        issued = datetime.fromisoformat(request["issued_at"])
        deadline = datetime.fromisoformat(request["deadline"])
        if not 0 < (deadline - issued).total_seconds() <= request["remaining_limits"]["max_execution_seconds"]:
            errors.append("stage request deadline exceeds remaining execution bound")
        if approval and issued < datetime.fromisoformat(approval["decided_at"]):
            errors.append("stage request issued before task approval")
        namespace = request["output_namespace"]
        required_prefix = f"artifacts/{execution['binding']['task_id']}/{execution['run_id']}/"
        if not namespace.startswith(required_prefix) or ".." in namespace.split("/"):
            errors.append("stage output namespace must stay within bound task/run")
        if request["stage"] in {"initial_baseline_evaluation", "llm_features", "comparison_and_freeze"}:
            development_only(request["released_input_refs"], "stage released inputs")
        elif request["stage"] == "final_validation":
            if not frozen or not frozen_result or frozen_result["parent_decision"]["decision"] != "proceed":
                errors.append("holdout release requires parent-authorized frozen choice")
        elif any(ref not in execution["source_refs"] and ref_key(ref) not in internal for ref in request["released_input_refs"]):
            errors.append("stage request releases inputs outside approved sources/artifacts")
    if report and report["outcome"] == "validation_failure":
        if not final or final["outcome"] != "fail" or report["final_validation_ref"] != record_ref(final):
            errors.append("measured validation failure needs actual failed-score evidence")
        elif final["parent_review"]["decision"] not in {"confirmed_failure", "stop"}:
            errors.append("terminal validation failure requires concluded parent review")
        elif final["defect_rechecks"] and final["defect_rechecks"][-1]["outcome"] == "execution_failure":
            errors.append("unresolved execution defect must use execution failure explanation")
    if report and report["outcome"] == "execution_failure":
        failed_stages = [s for s in by_kind.get("stage_result", []) if s["outcome"] == "execution_failed"]
        if not failed_stages or not report["failure"].get("error_code"):
            errors.append("execution failure requires typed failed stage/error evidence")
        elif not any(s["failure"]["error_code"] == report["failure"]["error_code"] for s in failed_stages):
            errors.append("execution failure contradicts observed stage error")
    verification = one("output_verification")
    if verification:
        if not report or verification["report_draft_ref"] != record_ref(report):
            errors.append("verifier must check the exact report draft")
        response = verification["permitted_response"]
        all_checks = verification["arithmetic_checks"] + verification["claim_checks"] + verification["binding_checks"]
        if verification["decision"] == "delivery_allowed":
            if report and report["outcome"] == "success" and report["parent_decision"]["decision"] != "proceed":
                errors.append("delivery requires parent authorization of report draft")
            if report and response["report_ref"] != record_ref(report):
                errors.append("permitted response references a different report")
            if any(c["status"] != "pass" for c in all_checks):
                errors.append("delivery blocked by failed/unavailable independent checks")
            if verification["parent_decision"]["decision"] != "proceed":
                errors.append("delivery requires parent proceed decision")
            if not verification["claim_checks"]:
                errors.append("delivery requires independent claim checks")
            if report and response["text"] != report["customer_draft"]:
                errors.append("permitted response changed verified draft")
            if report and report["outcome"] == "success":
                if response["kind"] != "final_report" or not verification["arithmetic_checks"]:
                    errors.append("successful delivery needs final report and independent arithmetic")
            elif response["kind"] not in {"failure_explanation", "missing_input_guidance"}:
                errors.append("failure path cannot deliver a valid recommendation list")
        elif response["kind"] != "no_customer_response" or response["text"]:
            errors.append("blocked verifier cannot authorize customer response")
    if execution:
        reviews = {digest(o) for r in records for o in walk(r)
                   if {"checkpoint", "decision", "actor", "decided_at", "reason", "evidence_refs"} == set(o)
                   and o["decision"] in {"review", "confirmed_failure", "allow_defect_recheck"}}
        if len(reviews) > execution["limits"]["max_parent_reviews"]:
            errors.append("parent review limit exhausted")
    return errors


def validate_bundle(bundle: dict) -> list[str]:
    """Validate component examples, preserving errors rather than executing work."""
    errors = []
    if bundle.get("schema_version") != VERSION:
        errors.append("bundle snapshot version mismatch")
    if bundle.get("fixture_provenance") != "mock" or not bundle.get("mock_notice"):
        errors.append("component fixtures require explicit mock provenance and notice")
    records = bundle.get("records", [])
    if not isinstance(records, list) or not records:
        return errors + ["bundle requires records"]
    for record in records:
        if record.get("provenance") != "mock":
            errors.append("all component fixture records must be mock")
    external_refs = []
    for artifact in bundle.get("mock_artifacts", []):
        ref = artifact.get("ref", {})
        ref_schema = {"$ref": "#/$defs/artifact_ref", "$defs": schema_validator().schema["$defs"]}
        ref_errors = list(schema_validator().evolve(schema=ref_schema).iter_errors(ref))
        if ref_errors or ref.get("provenance") != "mock":
            errors.append("mock artifact reference must be schema-valid and explicitly mock")
            continue
        if ref.get("sha256") != digest(artifact.get("content_marker")):
            errors.append("mock artifact digest does not identify its explicit fixture marker")
        external_refs.append(ref)
    if not errors:
        errors.extend(validate_handoff(records, external_refs))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    failed = False
    for name in args.paths:
        try:
            bundle = json.loads(Path(name).read_text())
            errors = validate_bundle(bundle)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors = [str(exc)]
        print(f"{name}: {'FAIL' if errors else 'PASS (mock contract only)'}")
        for error in errors:
            print(f"  {error}")
        failed |= bool(errors)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
