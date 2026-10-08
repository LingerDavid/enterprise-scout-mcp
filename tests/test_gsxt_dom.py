"""GSXT DOM search script helpers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from enterprise_scout_mcp.integrations.gsxt_dom import nodriver_search_script, submit_gsxt_dom_search_playwright


def test_nodriver_search_script_embeds_keyword_not_undefined():
    script = nodriver_search_script("苏州挚途")
    assert "undefined" not in script
    assert "苏州挚途" in script
    assert "setNativeValue" in script
    assert "#keyword" in script


def test_playwright_dom_search_uses_fill_not_destructure():
    page = MagicMock()
    loc = MagicMock()
    loc.first = loc
    loc.count = AsyncMock(return_value=1)
    loc.is_visible = AsyncMock(return_value=True)
    loc.scroll_into_view_if_needed = AsyncMock()
    loc.click = AsyncMock()
    loc.fill = AsyncMock()
    loc.evaluate = AsyncMock()
    loc.press = AsyncMock()
    page.locator = MagicMock(return_value=loc)

    btn = MagicMock()
    btn.first = btn
    btn.count = AsyncMock(return_value=1)
    btn.is_visible = AsyncMock(return_value=True)
    btn.click = AsyncMock()

    def locator_side_effect(sel: str):
        if sel in (".search_button", ".searchBtn", "#btn_query"):
            return btn
        return loc

    page.locator.side_effect = locator_side_effect
    page.evaluate = AsyncMock(return_value=False)

    result = asyncio.run(submit_gsxt_dom_search_playwright(page, "苏州挚途"))
    assert result["ok"] is True
    loc.fill.assert_awaited_once_with("苏州挚途")
    assert "undefined" not in str(loc.fill.call_args)
