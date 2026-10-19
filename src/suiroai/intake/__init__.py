"""DSC-25 receipt, understanding and version-bound sign-off conversation.

Expose file receipt and conversation helpers for forming the proposed task,
presenting it to the customer, and retaining an exact approved handoff.

Support the supply-files, propose-task, and sign-off loop, keeping material
assumptions and missing business facts attached to the confirmed task.

Linear: https://linear.app/gr3enarr0w/issue/DSC-25
"""
from .receipt import IntakeError, MeasuredInput, Receipt, SuppliedFile, receive_submission
from .roles import build_langchain_roles
from .conversation import (
    ConversationResult, Presentation, ProposalDraft, Response, approved_handoff,
    capture_response, draft_proposal, present_proposal,
)

__all__ = ["IntakeError", "MeasuredInput", "Receipt", "SuppliedFile", "receive_submission",
           "build_langchain_roles", "ConversationResult", "Presentation", "ProposalDraft",
           "Response", "approved_handoff", "capture_response", "draft_proposal", "present_proposal"]
