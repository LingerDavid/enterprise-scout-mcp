"""Fine UI scaffold detection."""

from enterprise_scout_mcp.diagnostics.verify import fine_ui_ready


def test_fine_ui_ready() -> None:
    assert fine_ui_ready() is True
