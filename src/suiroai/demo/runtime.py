"""Expose the actual native Data host for DSC-59 demo compatibility.

Development release isolation and current consent are enforced by the
investigation controller. This host uses the shared production native adapter;
there is no inventory-only stop or substituted analytical callback.

Linear: https://linear.app/gr3enarr0w/issue/DSC-59
"""
from suiroai.integration.native import NativeHost


class DemoNativeHost(NativeHost):
    """Use the same native execution path and evidence as the shared adapter."""
