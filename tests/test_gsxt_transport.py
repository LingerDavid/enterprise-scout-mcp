"""GSXT transport helpers — proxy + backend resolution."""

from __future__ import annotations

import os
from unittest.mock import patch

from enterprise_scout_mcp.config import GsxtConfig
from enterprise_scout_mcp.integrations.gsxt_browser import BrowserSearchResult
from enterprise_scout_mcp.integrations.gsxt_transport import (
    resolve_browser_backend,
    resolve_gsxt_proxy,
)
from enterprise_scout_mcp.transport.egress import EgressContext


def test_resolve_gsxt_proxy_prefers_egress():
    cfg = GsxtConfig(proxy_url="http://127.0.0.1:7897")
    egress = EgressContext(proxy_url="http://pool:8080")
    assert resolve_gsxt_proxy(cfg, egress) == "http://pool:8080"


def test_resolve_gsxt_proxy_config_then_env():
    cfg = GsxtConfig(proxy_url="http://127.0.0.1:7897", proxy_from_env=True)
    assert resolve_gsxt_proxy(cfg, None) == "http://127.0.0.1:7897"
    cfg2 = GsxtConfig(proxy_url="", proxy_from_env=True)
    with patch.dict(os.environ, {"HTTPS_PROXY": "http://env:3128"}, clear=False):
        assert resolve_gsxt_proxy(cfg2, None) == "http://env:3128"


def test_resolve_browser_backend_auto_cdp():
    cfg = GsxtConfig(browser_backend="auto", browser_cdp_port=9222)
    assert resolve_browser_backend(cfg) == "playwright_cdp"
    cfg2 = GsxtConfig(browser_backend="auto", browser_cdp_port=0)
    assert resolve_browser_backend(cfg2) == "nodriver"


def test_search_registry_browser_routes_playwright_cdp(monkeypatch):
    from pathlib import Path

    from enterprise_scout_mcp.integrations import gsxt_browser as mod

    cfg = GsxtConfig(browser_backend="playwright_cdp", browser_cdp_port=9222)
    called: dict[str, str] = {}

    def fake_cdp(keyword, **kwargs):
        called["keyword"] = keyword
        return BrowserSearchResult(ok=True, row={"name": "X", "credit_code": "91110000000000000X"})

    monkeypatch.setattr(
        "enterprise_scout_mcp.integrations.gsxt_playwright_cdp.search_registry_playwright_cdp",
        fake_cdp,
    )
    result = mod.search_registry_browser(
        "Acme",
        config=cfg,
        cookies={},
        user_data_dir=Path("."),
        index_url="https://www.gsxt.gov.cn/index.html",
    )
    assert result.ok is True
    assert called["keyword"] == "Acme"
