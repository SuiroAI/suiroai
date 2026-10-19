"""DSC-10: parent permissions for the single retail MVP.

Expose the parent workflow and guard errors used to enforce approved stage
permissions, checkpoint decisions, recovery bounds, and delivery gates.

Separate customer sign-off from internal run approval and retain control of
stage permissions, bounded recovery, and final response authorization.

Linear: https://linear.app/gr3enarr0w/issue/DSC-10
"""

from .workflow import GuardRejected, ParentWorkflow

__all__ = ["GuardRejected", "ParentWorkflow"]
