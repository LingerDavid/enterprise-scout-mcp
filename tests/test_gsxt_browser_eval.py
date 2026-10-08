"""Unit tests for in-browser API expression building (no live network)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from enterprise_scout_mcp.config import GsxtConfig
from enterprise_scout_mcp.integrations.gsxt_browser import (
    BrowserSearchResult,
    _inbrowser_api_search,
    search_registry_browser,
)


def test_inbrowser_api_search_embeds_args_in_expression():
    page = MagicMock()
    payload = {
        "status": 200,
        "text": json.dumps(
            {"data": [{"entName": "苏州挚途科技有限公司", "uniscId": "91320507MA1YW0G9XC"}]}
        ),
    }
    page.evaluate = AsyncMock(return_value=json.dumps(payload))
    cfg = GsxtConfig(
        search_url="https://www.gsxt.gov.cn/api/search/testAi",
        search_keyword_field="searchword",
    )
    row = asyncio.run(_inbrowser_api_search(page, "苏州挚途", cfg))
    assert row is not None
    assert row["credit_code"] == "91320507MA1YW0G9XC"
    expr = page.evaluate.call_args.args[0]
    assert "苏州挚途" in expr
    assert "testAi" in expr
    assert "searchword" in expr


def test_search_registry_browser_surfaces_import_error():
    from enterprise_scout_mcp.integrations import gsxt_browser as mod

    async def boom(*_a, **_k):
        raise ImportError("nodriver")

    with patch.object(mod, "search_registry_async", boom):
        result = search_registry_browser(
            "x",
            config=GsxtConfig(),
            cookies={"a": "b"},
            user_data_dir=MagicMock(),
            index_url="https://www.gsxt.gov.cn/index.html",
        )
    assert isinstance(result, BrowserSearchResult)
    assert result.ok is False
    assert "nodriver" in result.message
