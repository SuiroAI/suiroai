"""Stateless conversation artifacts. DSC-10 owns state and execution transitions."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from jsonschema import Draft202012Validator
from suiroai.contracts import VERSION, digest, proposal_digest, record_ref, validate_handoff, schema_validator
from .receipt import IntakeError, Receipt, checked, freeze
from .roles import NEEDS, HUMANIZER_SCHEMA, understanding_schema

OUTPUT = "one_restocking_list_and_final_report_or_verified_failure_explanation"


def _validate(value, schema):
    errors = list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise IntakeError("Invalid focused role output: " + "; ".join(e.message for e in errors))
    return value


def _call(role, context, schema):
    # No fallback, retries, tools or execution host. An LLM failure is not needs_inputs.
    encoded = freeze(context)
    if len(encoded.encode()) > 128 * 1024:
        raise IntakeError("Focused-call context exceeds 128 KiB; provide a bounded source description")
    return _validate(role.invoke({"context": encoded}), schema)


@dataclass(frozen=True)
class ProposalDraft:
    proposal_json: str | None
    understanding_json: str
    submission_ref_json: str

    @property
    def proposal(self):
        return json.loads(self.proposal_json) if self.proposal_json else None

    @property
    def understanding(self):
        return json.loads(self.understanding_json)


@dataclass(frozen=True)
class Presentation:
    """Parent-reviewed exact proposal/message snapshot, returned detached on reads."""
    packet_json: str

    @property
    def packet(self):
        return json.loads(self.packet_json)

    @property
    def proposal(self):
        return self.packet["proposal"]

    @property
    def message(self):
        return self.packet["customer_message"]


@dataclass(frozen=True)
class Response:
    """An explicit customer event, classified by the trusted conversation host.

    Ambiguous replies must use unclear. An approval with corrections or fresh
    material is a revision, not consent. No LLM may manufacture this event.
    """
    decision: str
    text: str
    actor: str
    at: str
    reply_to: dict
    has_material_changes: bool = False


@dataclass(frozen=True)
class ConversationResult:
    status: str
    approval_json: str
    message: str

    @property
    def approval(self):
        return json.loads(self.approval_json)


def draft_proposal(receipt: Receipt, *, understanding, proposal_version, clarifications=()):
    """Form step2 from the actual receipt. This does not present or advance it."""
    if type(proposal_version) is not int or proposal_version < 1:
        raise IntakeError("Positive parent-allocated proposal version required")
    submission = receipt.submission
    clarifications = tuple(clarifications)
    if any(not isinstance(event, Response) or not event.text.strip() or not event.actor.strip()
           for event in clarifications):
        raise IntakeError("Clarifications require actual attributed customer events")
    context = {"submission": submission, "inspections": receipt.inspections,
               "measured_source_refs": receipt.external_refs}
    if clarifications:
        context["customer_clarifications"] = [asdict(event) for event in clarifications]
    result = _call(understanding, context, understanding_schema())
    result = {**result, "assumptions": list(result["assumptions"])}
    for index, event in enumerate(clarifications, 1):
        result["assumptions"].append({
            "assumption_id": f"intake:customer-clarification:{index}",
            "classification": "supplied_fact", "status": "confirmed", "source_refs": [],
            "statement": f"Customer clarification from {event.actor} at {event.at}, replying to proposal {freeze(event.reply_to)}: {event.text}"})
    accessible = {s.file_id: s for s in receipt.sources}
    covered = set()
    for evidence in result["coverage"]:
        file_id = evidence["file_id"]
        if file_id is not None:
            source = accessible.get(file_id)
            if source is None or not evidence["columns"] or not set(evidence["columns"]) <= set(source.inspection["columns"]):
                raise IntakeError("Understanding claimed absent file/column evidence")
        else:
            quote = evidence["request_quote"]
            if not quote or not any(quote in text for text in
                                    [submission["original_request"], *(event.text for event in clarifications)]):
                raise IntakeError("Understanding needs an exact supplied request quote")
        covered.add(evidence["need"])
    for assumption in result["assumptions"]:
        if any(ref not in receipt.external_refs for ref in assumption["source_refs"]):
            raise IntakeError("Assumption cites absent or unmeasured source")
    if not result["supports_restocking"]:
        return ProposalDraft(None, freeze(result), freeze(receipt.ref))
    gaps = list(result["gaps"])
    for need, (what, why) in NEEDS.items():
        if need not in covered:
            gaps.append({"gap_id": f"intake:{need}", "description": f"Need {what.lower()} {why}.",
                         "material": True, "blocks": ["approval", "execution", "quantities"],
                         "request_to_user": f"Please provide {what.lower()} {why}."})
    for file in submission["files"]:
        if file["access"] != "accessible":
            gaps.append({"gap_id": f"intake:access:{file['file_id']}",
                         "description": f"{file['original_name']} is {file['access']}; it was not inspected.",
                         "material": True, "blocks": ["approval", "execution"],
                         "request_to_user": f"Provide an accessible copy of {file['original_name']} so its relevance and field meanings can be checked."})
    analytical_ids = ["intake:target-investigation", "intake:acceptance-rule"]
    for gap_id, description in zip(analytical_ids, (
        "Agent will investigate target/status/returns, duplicates, nonpositive quantities and sparse dates with lineage; absent dates are not presumed zero.",
        "Agent/parent must predeclare a measured acceptance rule before frozen final evaluation.")):
        gaps.append({"gap_id": gap_id, "description": description, "material": False,
                     "blocks": [], "request_to_user": "No customer statistical choice is required; the agent owns this investigation."})
    ids = [g["gap_id"] for g in gaps]
    if len(ids) != len(set(ids)):
        raise IntakeError("Duplicate gap identities")
    blocking = [g for g in gaps if g["material"] and set(g["blocks"]) & {"approval", "execution", "quantities"}]
    input_gap_ids = {f"intake:{need}" for need in NEEDS if need not in {"quantity_meaning", "review_context"}}
    has_missing_input = any(g["gap_id"] in input_gap_ids or g["gap_id"].startswith("intake:access:") for g in blocking)
    readiness = "needs_inputs" if has_missing_input else "needs_material_facts" if blocking else "ready"
    temporal = {key: value["const"] for key, value in schema_validator().schema["$defs"]["temporal_plan"]["properties"].items()}
    proposal = {"kind": "task_proposal", "schema_version": VERSION,
                "artifact_id": f"{submission['binding']['task_id']}:proposal", "artifact_version": proposal_version,
                "provenance": "mock" if submission["provenance"] == "mock" else "derived",
                "binding": {**submission["binding"], "proposal_version": proposal_version, "proposal_digest": "0" * 64},
                "submission_ref": receipt.ref, "goal": result["goal"], "output": OUTPUT,
                "source_refs": receipt.external_refs, "readiness": readiness,
                "assumptions": result["assumptions"], "gaps": gaps,
                "target_policy": {"status": "pending", "unresolved_gap_ids": [analytical_ids[0]]},
                "acceptance_rule": {"status": "pending", "unresolved_gap_ids": [analytical_ids[1]]},
                "temporal_plan": temporal}
    proposal["binding"]["proposal_digest"] = proposal_digest(proposal)
    checked(proposal)
    errors = validate_handoff([submission, proposal], receipt.external_refs)
    if errors:
        raise IntakeError("; ".join(errors))
    return ProposalDraft(freeze(proposal), freeze(result), freeze(receipt.ref))


def present_proposal(receipt: Receipt, draft: ProposalDraft, *, humanizer, parent_review):
    """Parent must verify the exact proposal AND customer text against sources.

    parent_review(packet, receipt) -> literal True. It must independently check
    semantics; an echo/LLM self-check is not independent source verification.
    """
    if json.loads(draft.submission_ref_json) != receipt.ref:
        raise IntakeError("Draft belongs to a different supplied input version")
    proposal = draft.proposal
    if proposal is None:
        message = "This MVP supports one historical retail restocking task. " + draft.understanding["goal"]
        status = "unsupported_task"
    else:
        summary = _call(humanizer, {"proposal": proposal, "understanding": draft.understanding,
                                  "inspections": receipt.inspections}, HUMANIZER_SCHEMA)["summary"]
        # Critical content is rendered verbatim outside humanization.
        lines = [summary, f"Proposed task v{proposal['binding']['proposal_version']}: {proposal['goal']}",
                 "Output: one restocking list and final report, or a verified explanation if this MVP cannot produce a reliable solution with the supplied data/scope.",
                 "Inputs: " + (", ".join(f"{f['original_name']} ({f['access']})" for f in receipt.submission["files"]) or "none supplied"),
                 "Review context: November 30, 2025; December is reserved unseen evaluation; same-product units."]
        lines.extend(f"{a['classification']}: {a['statement']}" for a in proposal["assumptions"])
        lines.extend(f"{g['description']} {g['request_to_user']}" for g in proposal["gaps"] if g["material"])
        lines.extend("Alternative requiring confirmation: " + a for a in draft.understanding["alternatives"])
        lines.append(f"Please confirm proposal v{proposal['binding']['proposal_version']}, or provide corrections/missing information for a revised proposal. No response means waiting; execution has not started.")
        message = "\n\n".join(lines)
        status = "awaiting_confirmation" if proposal["readiness"] == "ready" else proposal["readiness"]
    capability = proposal["readiness"] if proposal else "unsupported_task"
    if proposal and capability == "ready" and any(
            a["classification"] in {"supported_interpretation", "synthetic_assumption"}
            for a in proposal["assumptions"]):
        capability = "ready_with_assumptions"
    packet = {"status": status, "capability": capability, "proposal": proposal, "submission_ref": receipt.ref,
              "understanding": draft.understanding,
              "customer_message": message}
    packet["review_digest"] = digest(packet)
    if parent_review(json.loads(freeze(packet)), receipt) is not True:
        raise IntakeError("Parent source review did not approve this exact proposal/message")
    return Presentation(freeze(packet))


def capture_response(presentation: Presentation, *, response: Response | None,
                     current_submission: dict, current_proposal_ref: dict,
                     approval_version: int):
    """Serialize explicit consent; DSC-10 authenticates it and owns transitions."""
    proposal = presentation.proposal
    if proposal is None:
        raise IntakeError("Unsupported task has no sign-off proposal")
    if (proposal["submission_ref"] != record_ref(current_submission)
            or record_ref(proposal) != current_proposal_ref):
        raise IntakeError("Stale proposal or input version; repeat step2")
    decision, actor, at, comment = "pending", None, None, None
    status, message = "awaiting_confirmation", "Awaiting your confirmation; execution has not started."
    if response is not None:
        if response.reply_to != current_proposal_ref:
            raise IntakeError("Response does not bind to the current exact proposal")
        if response.decision not in {"approve", "reject", "correct", "new_material", "unclear"}:
            raise IntakeError("Unknown customer response; classify ambiguity as unclear")
        comment = response.text or None
        if response.has_material_changes or response.decision in {"reject", "correct", "new_material"}:
            decision, status = "rejected", "revise_proposal"
            actor, at = response.actor, response.at
            message = "I will review the correction/new information and present a revised proposal for sign-off. Execution has not started."
        elif response.decision == "approve":
            if proposal["readiness"] != "ready":
                status = proposal["readiness"]
                message = "The proposal still needs the listed inputs/business facts. I will revise it when those are supplied; execution has not started."
            else:
                decision, status, actor, at = "approved", "approved", response.actor, response.at
                message = f"Your sign-off is recorded for proposal v{proposal['binding']['proposal_version']}. The same proposal is available to the parent for its execution checks."
    approval = {"kind": "task_approval", "schema_version": VERSION,
                "artifact_id": f"{proposal['binding']['task_id']}:approval", "artifact_version": approval_version,
                "provenance": proposal["provenance"], "binding": proposal["binding"],
                "proposal_ref": current_proposal_ref, "decision": decision,
                "actor": actor, "decided_at": at, "comment": comment}
    checked(approval)
    errors = validate_handoff([current_submission, proposal, approval], proposal["source_refs"])
    if errors:
        raise IntakeError("; ".join(errors))
    return ConversationResult(status, freeze(approval), message)


def approved_handoff(receipt: Receipt, presentation: Presentation, result: ConversationResult,
                     *, current_submission, current_proposal_ref):
    """Return the SAME three records, never a post-approval task definition.

    Parent allocates run ID, bounds, execution contract and exact stage request.
    This function grants no execution permission and invokes no adapter.
    """
    proposal, approval = presentation.proposal, result.approval
    if (result.status != "approved" or approval["decision"] != "approved" or proposal is None
            or proposal["readiness"] != "ready" or receipt.submission != current_submission
            or proposal["submission_ref"] != receipt.ref or record_ref(proposal) != current_proposal_ref):
        raise IntakeError("Current version-bound approved proposal required")
    records = [receipt.submission, proposal, approval]
    errors = validate_handoff(records, receipt.external_refs)
    if errors:
        raise IntakeError("; ".join(errors))
    return records
