"""Camoufox fetch helpers (no live browser)."""

from __future__ import annotations

from enterprise_scout_mcp.integrations.camoufox_fetch import classify_aiqicha_html


def _extract(html: str) -> list:
    if "item-1" in html:
        return [{"aiqicha_id": "1", "company_name": "Acme"}]
    return []


def test_classify_captcha():
    status, rows = classify_aiqicha_html("需要安全验证 captcha", _extract)
    assert status == "captcha"
    assert rows == []


def test_classify_ok():
    status, rows = classify_aiqicha_html('card item-1 title="Acme"', _extract)
    assert status == "ok"
    assert rows[0]["company_name"] == "Acme"
