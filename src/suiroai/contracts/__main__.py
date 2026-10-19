"""Local contract-example checks, not an analytical runtime.

Expose the contract validator as a Python module command so developers can
check the supplied example bundles and inspect validation failures.

Support repeatable checks of the shared input/output contract before
components exchange approved-task and evidence records.

Linear: https://linear.app/gr3enarr0w/issue/DSC-24
"""
from .validation import main

raise SystemExit(main())
