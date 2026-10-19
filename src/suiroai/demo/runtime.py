"""Run genuine, bounded native discovery behind the DSC-59 adapter boundary.

The current integration stops before a model turn because the pinned parent
cannot release a development partition. Native discovery failures are retained
using the existing NativeHost evidence format; no mock runtime is substituted.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from pathlib import Path
import shutil
import time

from suiroai.integration.native import NativeHost, NativeRun
from suiroai.integration import native_profile as policy
from .worker import PREPARATION_BLOCKER


class DemoNativeHost(NativeHost):
    """Perform actual CLI discovery, then enforce the unresolved release guard.

    This is discovery only. It never starts an analytical thread or claims the
    full NativeHost execution profile has been verified.
    """

    def execute(self, *, cwd, prompt, evidence_dir, timeout_seconds,
                cancellation=None, mode="customer", released_root=None):
        run = NativeRun(mode=mode)
        run.evidence = {"mode": mode, "automatic_acceptance": False,
            "phase": "native_inventory_preflight", "analytical_model_turn_requested": False,
            "full_native_profile_verified": False}
        evidence_dir = Path(evidence_dir)
        allowed = False
        try:
            if mode != "customer" or released_root is None:
                raise policy.NativePolicyError("unsupported_integration", "Demo requires the real customer adapter boundary")
            policy.validate_roots(released_root, cwd, evidence_dir)
            allowed = True
            policy.validate_supported_plugin(self.plugin)
            if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (float, int)) or not 0 < timeout_seconds <= 3600:
                raise policy.NativePolicyError("budget_exhausted", "Positive bounded native discovery time required")
            executable = shutil.which(self.executable)
            if executable is None:
                raise policy.NativePolicyError("unsupported_integration", "Codex executable is unavailable")
            policy.bounded_plugin_inventory(executable, cwd,
                time.monotonic() + min(timeout_seconds, 20), run.evidence,
                self.plugin, cancellation)
            raise policy.NativePolicyError("unsupported_integration", PREPARATION_BLOCKER)
        except policy.NativePolicyError as exc:
            run.error_code, run.message = exc.code, str(exc)
        except (OSError, ValueError, TypeError) as exc:
            run.error_code, run.message = "runtime_error", str(exc)
        run.message, run.evidence = policy.sanitize(run.message), policy.sanitize(run.evidence)
        if allowed:
            self._write_evidence(run, evidence_dir)
        return run
