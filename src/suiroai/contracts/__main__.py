"""Local contract-example checks, not an analytical runtime.

Expose the contract validator as a Python module command so developers can
check the supplied example bundles and inspect validation failures.
"""
from .validation import main

raise SystemExit(main())
