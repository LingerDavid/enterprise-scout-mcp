"""Unit tests for in-browser Ruishu-safe search helpers."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from enterprise_scout_mcp.config import GsxtConfig
from enterprise_scout_mcp.integrations.gsxt_inbrowser import (
    is_ruishu_block_status,
    parse_inbrowser_payload,
    search_url_matcher,
)


def test_is_ruishu_block_status_codes():
    assert is_ruishu_block_status(521, "") is True
    assert is_ruishu_block_status(412, "") is True
    assert is_ruishu_block_status(405, "") is True
    assert is_ruishu_block_status(200, '{"ok":1}') is False


def test_parse_inbrowser_payload_ok():
    payload = {
        "status": 200,
        "text": json.dumps(
            {"data": [{"entName": "苏州挚途科技有限公司", "uniscId": "91320507MA1YW0G9XC"}]}
        ),
        "via": "native",
    }
    row = parse_inbrowser_payload(payload)
    assert row is not None
    assert row["credit_code"] == "91320507MA1YW0G9XC"


def test_parse_inbrowser_payload_rejects_521():
    payload = {"status": 521, "text": "<script>document.cookie=...</script>", "via": "fetch"}
    assert parse_inbrowser_payload(payload) is None


def test_search_url_matcher():
    cfg = GsxtConfig(search_url="https://www.gsxt.gov.cn/corp-query/search/testAi")
    match = search_url_matcher(cfg)
    resp = MagicMock()
    resp.url = "https://www.gsxt.gov.cn/corp-query/search/testAi?x=1"
    resp.request.method = "POST"
    assert match(resp) is True
    resp.request.method = "GET"
    assert match(resp) is False


def test_inbrowser_api_search_uses_evaluate():
    from enterprise_scout_mcp.integrations.gsxt_inbrowser import inbrowser_api_search

    page = MagicMock()
    page.evaluate = AsyncMock(
        return_value={
            "status": 200,
            "text": json.dumps(
                {"data": [{"entName": "Acme", "uniscId": "91110000000000000X"}]}
            ),
            "via": "native",
        }
    )
    row = asyncio.run(inbrowser_api_search(page, "Acme", GsxtConfig()))
    assert row is not None
    assert row["name"] == "Acme"
    args = page.evaluate.call_args.args
    assert "pajax" in args[0]
    assert args[1]["kw"] == "Acme"
