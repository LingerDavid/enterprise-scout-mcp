"""Shared East Money F10 HTTP helpers."""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.sources.cninfo import resolve_listing

F10_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://emweb.securities.eastmoney.com/",
    "User-Agent": "Mozilla/5.0",
}

F10_BASE = "https://emweb.securities.eastmoney.com/PC_HSF10"


def em_code(symbol_or_security: str) -> tuple[str, str] | None:
    """``600519.SH`` / ``SSE:600519`` → (``SH600519``, ``SSE:600519``)."""
    listing = resolve_listing(symbol_or_security)
    if listing is None:
        return None
    security_id, code, _column = listing
    exchange = security_id.split(":", 1)[0]
    prefix = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}.get(exchange, "")
    if not prefix:
        return None
    return f"{prefix}{code}", security_id


def fetch_f10_page(
    module: str,
    symbol_or_security: str,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """GET ``…/PC_HSF10/{module}/PageAjax``. Soft-fail → ``{}``."""
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {}
    em, _security_id = parsed
    own = client is None
    http = client or httpx.Client(timeout=20.0, headers=F10_HEADERS)
    try:
        resp = http.get(f"{F10_BASE}/{module}/PageAjax", params={"code": em})
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return {}
    finally:
        if own:
            http.close()
    return payload if isinstance(payload, dict) else {}


def date_str(value: Any) -> str:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else text
