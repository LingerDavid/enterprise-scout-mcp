"""Sidecar probe helpers (mocked HTTP)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from enterprise_scout_mcp.config import AppConfig
from enterprise_scout_mcp.diagnostics.sidecars import build_sidecar_report, probe_enscan


def test_probe_enscan_unreachable() -> None:
    with patch("enterprise_scout_mcp.diagnostics.sidecars.httpx.get", side_effect=OSError("refused")):
        report = probe_enscan("http://127.0.0.1:31000")
    assert report["reachable"] is False
    assert report["ok"] is False


def test_build_sidecar_report_skips_proxy_when_disabled() -> None:
    config = AppConfig()
    config.integrations.proxy_pool.enabled = False
    with patch("enterprise_scout_mcp.diagnostics.sidecars.probe_enscan") as ensan:
        ensan.return_value = {"reachable": True, "ok": True, "status_code": 200}
        report = build_sidecar_report(config)
    assert report["proxy_pool"]["skipped"] is True
