"""Map measured DSC-28 calculations to unchanged DSC-24 wire records.

Decisions are supplied by DSC-10. Draft records do not authenticate their own
parent fields; StageAdapter's trusted review still must adopt those claims.

Retain measured baseline, comparison, feature, and final-validation evidence
with immutable references so the parent can review each required model gate.

Linear: https://linear.app/gr3enarr0w/issue/DSC-28
"""
from __future__ import annotations

from datetime import date
from time import monotonic

from suiroai.contracts import VERSION, digest, record_ref, validate_record
from .core import CUTOFF, ModelingError, bound_payload, canonical, require_parent, finite
from .metrics import compare_values, metric_value
from .models import fit_model


def _provenance(execution, refs):
    return "mock" if execution["provenance"] == "mock" or any(r["provenance"] == "mock" for r in refs) else "derived"


def put_payload(store, execution, artifact_id, payload, refs=()):
    """Immutable private evidence carries the execution versions and source refs."""
    return store.put_bytes(artifact_id, 1, _provenance(execution, refs),
                           canonical(bound_payload(dict(payload, source_refs=list(refs)), execution)))


def _record(store, execution, kind, artifact_id, payload, refs):
    record = {"kind": kind, "schema_version": VERSION, "artifact_id": artifact_id,
              "artifact_version": 1, "provenance": _provenance(execution, refs),
              "binding": execution["binding"], "run_id": execution["run_id"], **payload}
    errors = validate_record(record)
    if errors:
        raise ModelingError("invalid modeling handoff: " + errors[0])
    store.put_record(record)
    return record


def persist_candidate(store, *, execution, artifact_id, measurement, feature_set_ref,
                      final_training, feature_names, remaining_fits, max_seconds):
    """Refit on development only, bounded separately from the rolling fit count.

    Persist before freezing. To retain the exact original initial candidate in
    step8, reuse this candidate record rather than replacing its fitted refs.
    """
    started = monotonic()
    if type(remaining_fits) is not int or remaining_fits < 1 or finite(max_seconds, "refit runtime") <= 0:
        raise ModelingError("final development refit budget exhausted")
    rows = tuple(final_training)
    if not rows or any(r.window.end > CUTOFF or r.label_available_on > CUTOFF for r in rows):
        raise ModelingError("final fit cannot use unavailable or December labels")
    feature_names=tuple(feature_names)
    if (not feature_names or len(set(feature_names))!=len(feature_names)
            or any(not isinstance(n,str) or not n for n in feature_names)
            or any(len(r.features)!=len(feature_names) for r in rows)):
        raise ModelingError("final fitted model requires its exact ordered feature names")
    if any(s["target_end_max"] > CUTOFF.isoformat() for s in measurement["scores"]):
        raise ModelingError("candidate measurements contain reserved targets")
    fitted = fit_model(measurement["model_kind"],rows,measurement["parameters"])
    if monotonic()-started > max_seconds:
        raise ModelingError("final refit runtime budget exhausted")
    state = fitted.payload()
    model_ref = put_payload(store, execution, artifact_id+"/model", {
        "format": "dsc28-fitted-model-v1", "state": state,
        "candidate_id": measurement["candidate_id"], "feature_names": list(feature_names),
        "fitted_folds": measurement["fitted_folds"], "rationale": measurement["rationale"]}, [feature_set_ref])
    preprocessing_ref = put_payload(store, execution, artifact_id+"/preprocessing", {
        "fit_scope": "training_fold_only", "final_fit_end": CUTOFF.isoformat(),
        "state": {k:state[k] for k in ("medians","centers","scales","imputation","standardization","all_missing_training_columns") if k in state},
        "fold_states": [{"fold_id": f["fold_id"], "training_end": f["training_end"],
                         "state": {k:f["model"][k] for k in ("medians","centers","scales") if k in f["model"]}}
                        for f in measurement["fitted_folds"]]}, [model_ref,feature_set_ref])
    evidence_ref = put_payload(store, execution, artifact_id+"/measured", measurement, [model_ref,feature_set_ref])
    return {"candidate_id": measurement["candidate_id"], "model_ref": model_ref,
            "feature_set_ref": feature_set_ref, "preprocessing_ref": preprocessing_ref,
            "scores": measurement["scores"], "eligible_for_selection": measurement["eligible_for_selection"],
            "evidence_refs": [evidence_ref]}, fitted


def initial_record(store, *, execution, preparation, artifact_id, plan, measured,
                   candidate, parent_decision):
    require_parent(preparation["parent_decision"], "preparation")
    require_parent(parent_decision, "initial_baseline_evaluation",
                   allowed=("proceed","stop","review"))
    primary = next((m for m in plan["metric_definitions"] if m["metric_id"] == plan["primary_metric_id"]), None)
    if (not primary or measured["primary_metric_id"] != primary["metric_id"]
            or measured["direction"] != primary["direction"] or measured["tie_tolerance"] != primary["tie_tolerance"]):
        raise ModelingError("measurement changed the declared evaluation metric/direction/tolerance")
    if candidate["candidate_id"] != measured["initial"]["candidate_id"] or candidate["scores"] != measured["initial"]["scores"]:
        raise ModelingError("initial candidate scores differ from measured evidence")
    comparison = compare_values(metric_value(measured["baseline"], primary["metric_id"]),
                                metric_value(measured["initial"], primary["metric_id"]),
                                primary["direction"],primary["tie_tolerance"])
    if measured["comparison"] != comparison:
        raise ModelingError("initial branch contradicts measured scores")
    return _record(store, execution, "initial_evaluation_result",artifact_id, {
        "execution_contract_ref": record_ref(execution), "preparation_result_ref": record_ref(preparation),
        "evaluation_plan": plan,"baseline_id": measured["baseline"]["candidate_id"],
        "baseline_scores": measured["baseline"]["scores"],"initial_candidate":candidate,
        "comparison":comparison,"parent_decision":parent_decision},
        [record_ref(preparation),*candidate["evidence_refs"]])


def comparison_record(store, *, execution, preparation, initial, feature_result,
                      artifact_id, measured, candidates, frozen, parent_decision,
                      checks, findings=(), bundle_ref=None):
    require_parent(initial["parent_decision"],"initial_baseline_evaluation")
    require_parent(feature_result["parent_decision"],"llm_features")
    require_parent(parent_decision,"comparison_and_freeze",allowed=("proceed","stop","review"))
    plan = initial["evaluation_plan"]
    primary = next((m for m in plan["metric_definitions"] if m["metric_id"] == plan["primary_metric_id"]), None)
    if (not primary or measured["primary_metric_id"] != primary["metric_id"]
            or measured["direction"] != primary["direction"] or measured["tie_tolerance"] != primary["tie_tolerance"]):
        raise ModelingError("shortlist changed predeclared metric/direction/tolerance")
    choices = measured["candidates"]
    if not choices:
        raise ModelingError("empty measured shortlist")
    winner = choices[0]
    for choice in choices[1:]:
        if compare_values(metric_value(winner,primary["metric_id"]),metric_value(choice,primary["metric_id"]),primary["direction"],primary["tie_tolerance"]) == "better":
            winner = choice
    if winner["candidate_id"] != measured["selected_candidate_id"]:
        raise ModelingError("shortlist winner contradicts actual measured ranking")
    feature_options = {digest(c["feature_set_ref"]) for c in candidates}
    if not {digest(preparation["initial_feature_set_ref"]),digest(feature_result["materialized_feature_set_ref"])} <= feature_options:
        raise ModelingError("comparison must measure original and augmented feature options")
    if (initial["initial_candidate"] not in candidates
            or {c["candidate_id"] for c in candidates} != {c["candidate_id"] for c in measured["candidates"]}
            or frozen["selected_candidate_id"] != measured["selected_candidate_id"]):
        raise ModelingError("comparison lost initial reference or changed measured winner")
    for candidate in candidates:
        actual = next(c for c in measured["candidates"] if c["candidate_id"] == candidate["candidate_id"])
        if candidate["scores"] != actual["scores"]:
            raise ModelingError("comparison candidate scores differ from measured evidence")
    selected=next((c for c in candidates if c["candidate_id"]==frozen["selected_candidate_id"]),None)
    if (not selected or not selected["eligible_for_selection"]
            or any(frozen[field]!=selected[field] for field in ("model_ref","feature_set_ref","preprocessing_ref"))
            or frozen["evaluation_plan_ref"]["sha256"]!=digest(plan)
            or frozen["acceptance_rule_ref"]["sha256"]!=digest(execution["acceptance_rule"])):
        raise ModelingError("freeze differs from measured selection or predeclared plan/rule")
    if len(candidates) > execution["limits"]["max_candidates"]:
        raise ModelingError("candidate limit exceeded")
    checks=list(checks)
    if bundle_ref is not None:
        from .frozen import verify_frozen
        bundle,_,_=verify_frozen(store,bundle_ref)
        if bundle["frozen"]!=frozen or bundle["execution_contract_sha256"]!=digest(execution):
            raise ModelingError("reviewed immutable bundle differs from selected frozen result")
        checks.append({"check_id":"immutable_freeze_binding","requirement_id":"DSC-28","status":"pass",
                       "expected":"exact frozen choice/plan/rule/forecast bytes are bound to approved task",
                       "actual":str(bundle["frozen_result_ref"]),
                       "evidence_refs":[bundle_ref,bundle["frozen_result_ref"]],"verifier":"dsc28-freeze-integrity"})
    elif execution["provenance"]!="mock":
        raise ModelingError("real comparison publication requires the reviewed immutable bundle reference")
    return _record(store,execution,"evaluation_result",artifact_id,{
        "execution_contract_ref":record_ref(execution),"preparation_result_ref":record_ref(preparation),
        "llm_feature_result_ref":record_ref(feature_result),"evaluation_plan":plan,
        "baseline_id":initial["baseline_id"],"baseline_scores":initial["baseline_scores"],
        "initial_candidate_id":initial["initial_candidate"]["candidate_id"],"candidates":candidates,
        "selection_rule":"Measured declared primary metric; earlier predeclared original-feature candidate wins ties.",
        "comparison_checks":list(checks),"frozen":frozen,"findings":list(findings),"parent_decision":parent_decision},
        [record_ref(preparation),record_ref(initial),record_ref(feature_result)])


def final_record(store, *, execution, evaluation, artifact_id, evidence, parent_review,
                 defect_rechecks=(), findings=()):
    """Valid scores only; unmeasured failures use the stage failure variant."""
    require_parent(evaluation["parent_decision"],"comparison_and_freeze")
    require_parent(parent_review,"final_validation",allowed=("proceed","stop","confirmed_failure","allow_defect_recheck","pass_after_recheck"))
    frozen=evaluation["frozen"]
    if (evidence["binding"]!=execution["binding"] or evidence["run_id"]!=execution["run_id"]
            or evidence["execution_contract_sha256"]!=digest(execution)):
        raise ModelingError("final evidence changed task/run/execution binding")
    if evidence["acceptance_rule"] != execution["acceptance_rule"]:
        raise ModelingError("final acceptance rule differs from approved rule")
    if evidence["frozen_result_ref"]["sha256"] != digest(frozen):
        raise ModelingError("final evidence changed frozen selection")
    if (evidence["outcome"] == "pass") != (parent_review["decision"] in {"proceed", "pass_after_recheck"}):
        raise ModelingError("parent final review contradicts measured outcome")
    if (evidence["november_30_forecast_ref"] != frozen["november_30_forecast_ref"]
            or not evidence["scores"]):
        raise ModelingError("final evidence has no measured scores or changed forecast")
    return _record(store,execution,"final_validation_result",artifact_id,{
        "execution_contract_ref":record_ref(execution),"evaluation_result_ref":record_ref(evaluation),
        "frozen_result_ref":evidence["frozen_result_ref"],
        "november_30_forecast_ref":frozen["november_30_forecast_ref"],
        "acceptance_rule":execution["acceptance_rule"],"reserved_unseen_data_ref":evidence["reserved_unseen_data_ref"],
        "scores":evidence["scores"],"checks":evidence["checks"],"outcome":evidence["outcome"],
        "parent_review":parent_review,"defect_rechecks":list(defect_rechecks),"findings":list(findings),
        "holdout_accessed_at":evidence["holdout_accessed_at"]},
        [record_ref(evaluation),evidence["november_30_forecast_ref"],evidence["reserved_unseen_data_ref"]])


def feature_records(store, *, execution, preparation, initial, artifact_id,
                    generated, materialized, parent_decision, findings=()):
    """Persist one LLM proposal and its checked original+additional feature set."""
    require_parent(initial["parent_decision"],"initial_baseline_evaluation")
    require_parent(parent_decision,"llm_features",allowed=("proceed","stop","review"))
    if (generated["binding"] != execution["binding"] or generated["run_id"] != execution["run_id"]
            or generated["initial_evaluation_ref"] != record_ref(initial)
            or generated["preparation_result_ref"] != record_ref(preparation)
            or generated["execution_contract_sha256"] != digest(execution)
            or generated["definitions"] != materialized["definitions"]
            or generated["original_feature_set_ref"] != preparation["initial_feature_set_ref"]
            or generated["initial_feature_fields"] != materialized["initial_feature_fields"]):
        raise ModelingError("feature generation/materialization changed approved context or definitions")
    if any(row["origin"] > CUTOFF.isoformat() for row in materialized["rows"]):
        raise ModelingError("development feature materialization contains future origins")
    from .features import materialize_features
    import json
    import hashlib
    if (hashlib.sha256(generated["prompt"].encode()).hexdigest()!=generated["prompt_sha256"]
            or hashlib.sha256(generated["response"].encode()).hexdigest()!=generated["response_sha256"]):
        raise ModelingError("LLM call evidence changed after generation")
    response=json.loads(generated["response"])
    if response != {"definitions":generated["definitions"]}:
        raise ModelingError("stored definitions differ from actual LLM response")
    fields=generated["initial_feature_fields"]
    columns=["Product_ID","Store_ID","origin",*fields]
    originals=[{c:r[c] for c in columns} for r in materialized["rows"]]
    initial_payload=json.loads(store.read_bytes(preparation["initial_feature_set_ref"]))
    if initial_payload.get("format") != "dsc27-initial-v1":
        raise ModelingError("materialization requires actual original prepared feature bytes")
    original_index={(r["Product_ID"],r["Store_ID"],r["origin"]):r for r in initial_payload["rows"]}
    for row in originals:
        source=original_index.get((row["Product_ID"],row["Store_ID"],row["origin"]))
        if not source or any(source.get(f)!=row[f] for f in fields):
            raise ModelingError("materialized original values differ from prepared features")
    recalculated=materialize_features(originals,generated["definitions"],initial_feature_fields=fields,source_refs=generated["development_context_refs"])
    if recalculated != materialized:
        raise ModelingError("materialized feature outputs/checks changed after calculation")
    provenance="mock" if generated["provenance"]=="mock" else _provenance(execution,generated["development_context_refs"])
    prompt_ref=store.put_bytes(artifact_id+"/prompt",1,provenance,generated["prompt"].encode())
    response_ref=store.put_bytes(artifact_id+"/response",1,provenance,generated["response"].encode())
    if (prompt_ref["sha256"] != generated["prompt_sha256"] or response_ref["sha256"] != generated["response_sha256"]):
        raise ModelingError("LLM call evidence changed after generation")
    proposal=_record(store,execution,"feature_proposal",artifact_id+"/proposal",{
        "execution_contract_ref":record_ref(execution),"preparation_result_ref":record_ref(preparation),
        "generation":{"generation_kind":"llm_generated","model_id":generated["model_id"],
                      "prompt_ref":prompt_ref,"response_ref":response_ref,"generated_at":generated["generated_at"],
                      "development_context_refs":generated["development_context_refs"],"unrestricted_raw_future_access":False},
        "definitions":generated["definitions"],"initial_evaluation_ref":record_ref(initial)},
        [record_ref(initial),prompt_ref,response_ref,*generated["development_context_refs"]])
    inputs=[preparation["initial_feature_set_ref"],record_ref(proposal),generated["stage_request_ref"],*generated["development_context_refs"]]
    materialized_ref=put_payload(store,execution,artifact_id+"/materialized",materialized,inputs)
    checks_ref=put_payload(store,execution,artifact_id+"/checks",materialized["checks"],[materialized_ref])
    raw_hashes=sorted({h for line in preparation["lineage"] for h in line["preserved_raw_hashes"]})
    if not raw_hashes:
        raise ModelingError("feature result must retain original raw source lineage")
    passed=all(materialized["checks"].get(k) is True for k in ("identity_alignment","original_values_preserved","calculation_rechecked","finite_or_explicit_null","stateless_no_fitted_parameters"))
    check={"check_id":"llm_feature_outputs","requirement_id":"DSC-28","status":"pass" if passed else "fail",
           "expected":"finite or explicit null, exact original alignment, reproducible origin-safe additional transforms",
           "actual":str(materialized["checks"]),"evidence_refs":[checks_ref],"verifier":"dsc28-feature-materializer"}
    origins=[row["origin"] for row in materialized["rows"]]
    availability={"artifact_ref":materialized_ref,"permitted_use":"development",
                  "earliest_event_date":min(origins),"latest_event_date":max(origins),
                  "latest_information_available_date":max(origins),"event_time_column":"origin",
                  "availability_time_column":"origin","contains_post_cutoff_rows":False}
    result=_record(store,execution,"feature_result",artifact_id+"/result",{
        "feature_proposal_ref":record_ref(proposal),"materialized_feature_set_ref":materialized_ref,
        "definitions":generated["definitions"],"lineage":[{"output_ref":materialized_ref,"input_refs":inputs,
        "transformation_id":"dsc28-declarative-features-v1","description":materialized["inference_behavior"],
        "row_lineage_ref":checks_ref,"preserved_raw_hashes":raw_hashes}],
        "availability":[*generated["context_availability"],availability],"validation_checks":[check],
        "findings":list(findings),"parent_decision":parent_decision},[record_ref(proposal),materialized_ref])
    return proposal,result
