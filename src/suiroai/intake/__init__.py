"""DSC-25 receipt, understanding and version-bound sign-off conversation.

Expose file receipt and conversation helpers for forming the proposed task,
presenting it to the customer, and retaining an exact approved handoff.
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
