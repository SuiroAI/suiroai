"""Compose one reviewable narrative from immutable contract evidence.

An optional focused humanizer selects the ordering of complete, evidence-bound
sentences. Its output cannot add, omit or rewrite a claim. A LangChain structured
output callable can implement this interface; no host/API is assumed here.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Callable

from suiroai.contracts.validation import record_ref
from suiroai.replenishment.context import Handoff, InputError

Humanizer = Callable[[list[dict]], list[str]]
SCOPE = "This MVP could not produce a reliable solution with the supplied data and scope."


def _text(value: str) -> str:
    # Findings are already customer-facing upstream artifacts, never raw logs.
    if not isinstance(value, str) or not value.strip() or len(value) > 1200 or "```" in value or any(ord(c) < 32 or ord(c) == 127 or c in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069" for c in value):
        raise InputError("Customer evidence must be concise, single-paragraph text, not code or logs")
    return value


def _product_name(value: str) -> str:
    value = _text(value)
    if len(value) > 256 or any(c in value for c in "<>[]`"):
        raise InputError("Approved product name contains unsafe presentation text")
    return value


def _authorize(h: Handoff, record: dict, field: str, decisions: set[str], checkpoint: str) -> None:
    decision = record.get(field)
    if not decision or decision.get("checkpoint") != checkpoint:
        raise InputError(f"Parent authorization must attest the exact {checkpoint} checkpoint")
    h.authorize(record, field, decisions)


def _claim(claim_id: str, statement: str, refs: list[dict]) -> dict:
    return {"claim_id": claim_id, "statement": _text(statement), "evidence_refs": deepcopy(refs)}


def _compose(claims: list[dict], humanizer: Humanizer | None) -> str:
    ids = [c["claim_id"] for c in claims]
    selected = humanizer(deepcopy(claims)) if humanizer else ids
    if not isinstance(selected, list) or len(selected) != len(ids) or any(not isinstance(i, str) for i in selected) or set(selected) != set(ids):
        raise InputError("Humanizer must return each supplied claim ID exactly once; new prose is not permitted")
    by_id = {c["claim_id"]: c["statement"] for c in claims}
    return "\n\n".join(by_id[i] for i in selected)


def _start(h: Handoff, artifact_id: str, version: int, decision: dict, outcome: str) -> dict:
    h.validate()
    execution = h.one("execution_contract")
    if "draft_report" not in execution["allowed_actions"]:
        raise InputError("Approved execution contract does not allow draft_report")
    result = h.envelope("report_draft", artifact_id, version)
    result.update(execution_contract_ref=record_ref(execution), outcome=outcome,
                  final_validation_ref=None, frozen_result_ref=None,
                  november_30_forecast_ref=None, arithmetic_source_refs=[],
                  orders=[], exceptions=[], arithmetic_checks=[], claims=[],
                  findings=[], customer_draft="", failure=None,
                  parent_decision=deepcopy(decision), quantity_result_ref=None)
    return result


def _resolve(h: Handoff, ref: dict) -> dict:
    return h.record(ref)


def _verify_refs(h: Handoff, refs: list[dict]) -> None:
    """Resolve each claimed evidence chain and check its external byte hashes."""
    seen = set()

    def visit(value):
        if isinstance(value, dict):
            if set(value) == {"artifact_id", "version", "sha256", "provenance"}:
                identity = (value["artifact_id"], value["version"], value["sha256"])
                if identity in seen:
                    return
                seen.add(identity)
                if value in h.external_refs:
                    h.read(value)
                else:
                    visit(h.record(value))
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(refs)


def _finish(h: Handoff, result: dict, claims: list[dict], humanizer: Humanizer | None) -> dict:
    if result["provenance"] == "mock" and not any(c["claim_id"] == "mock-notice" for c in claims):
        claims.insert(0, _claim("mock-notice", "MOCK DEVELOPMENT EXAMPLE ONLY: these artifacts do not establish real analytical or execution acceptance.", [result["execution_contract_ref"]]))
    _verify_refs(h, [ref for claim in claims for ref in claim["evidence_refs"]])
    result["claims"] = claims
    result["customer_draft"] = _compose(claims, humanizer)
    h.finish(result)
    return result


def _scores(prefix: str, label: str, scores: list[dict], refs: list[dict]) -> list[dict]:
    return [_claim(f"{prefix}-{i}",
                   f"{label}: {s['metric_id']} = {s['value']} {s['unit']}; population {s['population_id']}, "
                   f"{s['observation_count']} observations, forecast origins {s['forecast_origin_start']} to "
                   f"{s['forecast_origin_end']}, latest target end {s['target_end_max']}.", refs)
            for i, s in enumerate(scores)]


def draft_success(h: Handoff, *, artifact_id: str,
                  version: int = 1, humanizer: Humanizer | None = None) -> dict:
    """Consume exact independently checked, parent-approved quantities, never calculate."""
    h.validate()
    quantity = h.one("quantity_result")
    result = _start(h, artifact_id, version, quantity["parent_decision"], "success")
    final = h.one("final_validation_result")
    if final["outcome"] != "pass":
        raise InputError("Successful recommendation drafting requires passed final validation")
    _authorize(h, final, "parent_review", {"proceed", "pass_after_recheck"}, "final_validation")
    _authorize(h, quantity, "parent_decision", {"proceed"}, "recommendations")
    candidate_ref = quantity["candidate_quantity_ref"]
    if not candidate_ref or not quantity["independent_check_refs"]:
        raise InputError("Numerical parent approval must bind independent candidate checks")
    checks = []
    for ref in quantity["independent_check_refs"]:
        evidence = _resolve(h, ref)
        if evidence["kind"] != "evidence_record" or candidate_ref not in evidence["checked_artifacts"] or evidence["check"]["status"] != "pass" or evidence["verifier_decision"] != "accepted":
            raise InputError("Independent numerical evidence must accept the exact candidate quantity version")
        checks.append(deepcopy(evidence["check"]))
    if any(row["approved_order_quantity"] is None for row in quantity["orders"]):
        raise InputError("Cannot humanize unapproved numerical rows")
    quantity_ref = record_ref(quantity)
    for field in ("final_validation_ref", "frozen_result_ref", "november_30_forecast_ref", "arithmetic_source_refs", "orders", "exceptions"):
        result[field] = deepcopy(quantity[field])
    result["arithmetic_checks"] = checks
    result["quantity_result_ref"] = quantity_ref
    execution = h.one("execution_contract")
    if not execution["synthetic_operational_source_refs"]:
        raise InputError("This illustrative report requires declared synthetic operational inputs")
    claims = [_claim("synthetic", "Inventory, incoming receipts and purchasing policies are synthetic; these restocking recommendations are illustrative.", execution["synthetic_operational_source_refs"])]
    if h.one("execution_contract")["provenance"] == "mock":
        claims.insert(0, _claim("mock-notice", "MOCK DEVELOPMENT EXAMPLE ONLY: these artifacts do not establish real analytical or execution acceptance.", [record_ref(execution)]))
    if not quantity["orders"]:
        claims.append(_claim("empty-orders", "No order rows were approved for this run.", [quantity_ref]))
    if any(row.get("product_name") is None for row in quantity["orders"]):
        claims.append(_claim("missing-product-name-mapping", "No verified product-name mapping was supplied for some approved rows; those items are identified by source, product ID and store ID.", [quantity_ref]))
    for i, row in enumerate(quantity["orders"]):
        key = row["key"]
        name = f"; product name {_product_name(row['product_name'])}" if row.get("product_name") is not None else ""
        claims.append(_claim(f"order-{i}",
            f"Source {key['source_namespace']}; product ID {key['product_id']}{name}; store ID {key['store_id']}: "
            f"approved order {row['approved_order_quantity']} {row['quantity_unit']} for "
            f"{row['forecast_horizon_start']} through {row['forecast_horizon_end']}.", [quantity_ref]))
    for i, exception in enumerate(quantity["exceptions"]):
        key = exception["key"]
        claims.append(_claim(f"exception-{i}", f"Unresolved exception for source {key['source_namespace']}, product ID {key['product_id']}, store ID {key['store_id']}: {_text(exception['reason'])}", [quantity_ref, *exception["evidence_refs"]]))
    preparation = h.one("preparation_result")
    feature = h.one("feature_result")
    evaluation = h.one("evaluation_result")
    for source, checkpoint in ((preparation, "preparation"), (feature, "llm_features"), (evaluation, "comparison_and_freeze")):
        _authorize(h, source, "parent_decision", {"proceed"}, checkpoint)
    for category, source in (("data-treatment-and-EDA", preparation), ("generated-features", feature), ("comparison", evaluation), ("unseen", final)):
        findings = [f for f in source["findings"] if f["audience"] == "final_report"]
        if not findings:
            raise InputError(f"Missing evidence-backed final-report findings: {category}")
        for i, finding in enumerate(findings):
            result["findings"].append(deepcopy(finding))
            claims.append(_claim(f"{category}-{i}", finding["statement"], [record_ref(source), *finding["evidence_refs"]]))
    for i, definition in enumerate(feature["definitions"]):
        claims.append(_claim(f"generated-feature-definition-{i}",
            f"LLM-generated feature {definition['name']}. Proposed rationale: {_text(definition['rationale'])} "
            f"Availability rule: {_text(definition['timing_rule'])}", [record_ref(feature), *definition["source_refs"]]))
    if not any(f["classification"] == "material_limitation" for f in result["findings"]):
        raise InputError("Final report requires evidenced material limitations")
    evaluation_ref, final_ref = record_ref(evaluation), record_ref(final)
    claims.extend(_scores("baseline", f"Development baseline {evaluation['baseline_id']}", evaluation["baseline_scores"], [evaluation_ref]))
    for i, candidate in enumerate(evaluation["candidates"]):
        claims.extend(_scores(f"candidate-{i}", f"Development candidate {candidate['candidate_id']}", candidate["scores"], [evaluation_ref]))
    claims.append(_claim("frozen-choice", f"The frozen selected candidate is {evaluation['frozen']['selected_candidate_id']}.", [evaluation_ref]))
    claims.extend(_scores("unseen-score", "Reserved unseen evaluation", final["scores"], [final_ref]))
    claims.append(_claim("unseen-outcome", "The frozen model passed the predeclared final validation rule.", [final_ref]))
    return _finish(h, result, claims, humanizer)


def draft_validation_failure(h: Handoff, *, artifact_id: str,
                             version: int = 1) -> dict:
    h.validate()
    final = h.one("final_validation_result")
    result = _start(h, artifact_id, version, final["parent_review"], "validation_failure")
    if final["outcome"] != "fail":
        raise InputError("Measured failure explanation requires failed final validation")
    _authorize(h, final, "parent_review", {"confirmed_failure", "stop"}, "final_validation")
    if final["defect_rechecks"] and final["defect_rechecks"][-1]["outcome"] == "execution_failure":
        raise InputError("Unresolved execution failure must use execution failure draft")
    ref = record_ref(final)
    for field in ("frozen_result_ref", "november_30_forecast_ref"):
        result[field] = deepcopy(final[field])
    result["final_validation_ref"] = ref
    reason = "The frozen model failed the predeclared reserved unseen validation rule; parent review concluded this run."
    result["failure"] = {"stage": "final_validation", "reason": reason, "scope_limitation": SCOPE, "evidence_refs": [ref]}
    claims = [_claim("terminal-scope", SCOPE, [ref]), _claim("measured-failure", reason, [ref])]
    claims.extend(_scores("failed-score", "Reserved unseen evaluation", final["scores"], [ref]))
    rule = final["acceptance_rule"]
    for i, gate in enumerate(rule["metric_gates"]):
        claims.append(_claim(f"failed-gate-{i}",
            f"Predeclared metric gate {gate['metric_id']}: direction {gate['direction']}, threshold {gate['threshold']} {gate['unit']}, "
            f"population {gate['population_id']}, aggregation {gate['aggregation']}; minimum observation count {rule['minimum_observation_count']}.", [ref]))
    required = {check["check_id"]: check["status"] for check in final["checks"]}
    for i, check_id in enumerate(rule["required_check_ids"]):
        claims.append(_claim(f"required-check-{i}", f"Required validation check {check_id}: {required.get(check_id, 'unavailable')}.", [ref]))
    claims.append(_claim("no-list", "No reliable restocking list is available from this run.", [ref]))
    return _finish(h, result, claims, None)


def draft_execution_failure(h: Handoff, *, artifact_id: str, failed_stage_ref: dict,
                            version: int = 1) -> dict:
    h.validate()
    stage = _resolve(h, failed_stage_ref)
    if stage["kind"] != "stage_result" or stage["outcome"] != "execution_failed":
        raise InputError("Execution explanation requires the exact observed failed stage")
    result = _start(h, artifact_id, version, stage["parent_decision"], "execution_failure")
    _authorize(h, stage, "parent_decision", {"stop", "confirmed_failure"}, stage["stage"])
    code = stage["failure"]["error_code"]
    # The typed failure reason binds the exact observed field. Presentation
    # context belongs in the customer claim, never in this immutable fact.
    reason = _text(stage["failure"]["reason"])
    status = f"Execution ended at stage {stage['stage']} with error category {code}; parent review concluded this run. Observed reason: {reason}"
    result["failure"] = {"stage": stage["failure"]["stage"], "reason": reason, "scope_limitation": SCOPE, "evidence_refs": [failed_stage_ref], "error_code": code}
    return _finish(h, result, [_claim("terminal-scope", SCOPE, [failed_stage_ref]), _claim("execution-error", status, [failed_stage_ref]), _claim("no-list", "No reliable restocking list is available from this run.", [failed_stage_ref])], None)


def draft_missing_inputs(h: Handoff, *, source_ref: dict | None = None) -> dict:
    """Pre-signoff guidance is local, not a fabricated execution-derived report.

    A DSC-24 report_draft requires an execution contract, even for missing_inputs;
    native intake guidance is therefore a separate local return value until that
    owner provides a pre-execution envelope. No execution/approval is invented.
    """
    h.validate()
    source = _resolve(h, source_ref) if source_ref else h.one("task_proposal")
    if source["kind"] == "task_proposal":
        if source["readiness"] != "needs_inputs":
            raise InputError("Missing-input guidance requires declared proposal gaps")
    elif source["kind"] != "stage_result" or source["outcome"] not in {"needs_inputs", "needs_material_facts"}:
        raise InputError("Missing-input guidance requires proposal or observed stage gaps")
    gaps = [g for g in source["gaps"] if g["material"]]
    if not gaps:
        raise InputError("No material evidence-backed gaps were supplied")
    ref = record_ref(source)
    claims = [_claim(f"gap-{i}", f"{_text(g['description'])} Needed: {_text(g['request_to_user'])} Blocks: {', '.join(g['blocks']) or 'readiness review'}.", [ref]) for i, g in enumerate(gaps)]
    proposal = source if source["kind"] == "task_proposal" else h.one("task_proposal")
    submission = h.one("submission")
    proposal_ref, submission_ref = record_ref(proposal), record_ref(submission)
    accessible = [file for file in submission["files"] if file["access"] == "accessible"]
    accessible_refs = []
    for file in accessible:
        matches = [external for external in h.external_refs
                   if external["artifact_id"] == file["file_id"] and external["sha256"] == file["sha256"]
                   and external["provenance"] == file["provenance"]]
        if len(matches) != 1:
            raise InputError("Accessible-source capability guidance requires exact bound source bytes")
        accessible_refs.append(matches[0])
    claims.insert(0, _claim("unsupported-goal", f"The following proposed goal is currently blocked by the documented input gaps: {_text(proposal['goal'])}", [proposal_ref, ref]))
    if accessible:
        claims.append(_claim("supported-capability", "Current supported work is limited to read-only inspection of the actually accessible supplied sources.", [submission_ref]))
        for i, file in enumerate(accessible):
            claims.append(_claim(f"accessible-source-{i}", f"Accessible source: {_text(file['original_name'])}; declared role {_text(file['source_role'])}.", [submission_ref, accessible_refs[i]]))
    else:
        claims.append(_claim("supported-capability", "No supplied source is currently accessible for read-only inspection.", [submission_ref]))
    claims.append(_claim("next-step", "Next step: provide the requested files or material facts above, then review the updated proposal for the same business goal before execution.", [ref, proposal_ref]))
    if source["provenance"] == "mock":
        claims.insert(0, _claim("mock-notice", "MOCK DEVELOPMENT EXAMPLE ONLY: no real input assessment or execution is established.", [ref]))
    _verify_refs(h, [ref, proposal_ref, submission_ref, *accessible_refs])
    return {"outcome": "missing_inputs", "contract_status": "component_local_pre_execution_guidance",
            "source_ref": ref, "binding": deepcopy(source["binding"]), "gaps": deepcopy(gaps),
            "claims": claims, "customer_draft": _compose(claims, None), "orders": [],
            "delivery_authorized": False}
