"""DSC-29 candidate arithmetic; no model selection or approval authority.

Expose the handoff checks and calculation entry point that turn frozen
forecasts and operational inputs into reviewable candidate purchase quantities.

Keep candidate quantity calculation separate from report wording so parent
checks can approve arithmetic before the customer response is composed.

Linear: https://linear.app/gr3enarr0w/issue/DSC-29
"""

from .context import Handoff, InputError
from .calculation import calculate_candidate

__all__ = ["Handoff", "InputError", "calculate_candidate"]
