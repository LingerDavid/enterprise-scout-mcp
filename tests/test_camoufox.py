"""Camoufox backend — availability gate without requiring the package."""

from __future__ import annotations

import pytest

from enterprise_scout_mcp.transport.camoufox_backend import CamoufoxTransport, camoufox_available


def test_camoufox_status_shape() -> None:
    st = camoufox_available()
    assert isinstance(st.available, bool)
    assert isinstance(st.message, str)


def test_launch_raises_when_missing() -> None:
    st = camoufox_available()
    if st.available:
        pytest.skip("camoufox installed — skip missing-package path")
    transport = CamoufoxTransport()
    with pytest.raises(RuntimeError, match="camoufox"):
        transport.launch_sync()
