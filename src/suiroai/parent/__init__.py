"""DSC-10: parent permissions for the single retail MVP.

Expose the parent workflow and guard errors used to enforce approved stage
permissions, checkpoint decisions, recovery bounds, and delivery gates.
"""

from .workflow import GuardRejected, ParentWorkflow

__all__ = ["GuardRejected", "ParentWorkflow"]
