"""East Money F10 company survey → credit code + issuer name."""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.sources.cninfo import resolve_listing

_SURVEY_URL = "https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax"
_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://emweb.securities.eastmoney.com/",
    "User-Agent": "Mozilla/5.0",
}


def _em_code(symbol_or_security: str) -> str | None:
    listing = resolve_listing(symbol_or_security)
    if listing is None:
        return None
    security_id, code, _column = listing
    exchange = security_id.split(":", 1)[0]
    prefix = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}.get(exchange, "")
    if not prefix:
        return None
    return f"{prefix}{code}"


def profile_from_survey_payload(payload: dict[str, Any]) -> dict[str, str]:
    """Extract credit_code / name / industry from CompanySurvey JSON."""
    items = payload.get("jbzl") if isinstance(payload, dict) else None
    row: dict[str, Any] = {}
    if isinstance(items, list) and items and isinstance(items[0], dict):
        row = items[0]
    elif isinstance(items, dict):
        row = items
    credit = str(row.get("REG_NUM") or "").strip()
    name = str(row.get("ORG_NAME") or row.get("SECURITY_NAME_ABBR") or "").strip()
    industry = str(row.get("INDUSTRYCSRC1") or "").strip()
    l1, l2 = "", ""
    if industry and "-" in industry:
        l1, l2 = industry.split("-", 1)
        l1, l2 = l1.strip(), l2.strip()
    elif industry:
        l1 = industry
    return {
        "credit_code": credit,
        "issuer_name": name,
        "csrc_industry_l1": l1,
        "csrc_industry_l2": l2,
    }


def fetch_company_profile(
    symbol_or_security: str,
    *,
    client: httpx.Client | None = None,
) -> dict[str, str]:
    """Live CompanySurvey pull. Soft-fail → empty strings."""
    em_code = _em_code(symbol_or_security)
    empty = {
        "credit_code": "",
        "issuer_name": "",
        "csrc_industry_l1": "",
        "csrc_industry_l2": "",
    }
    if not em_code:
        return empty
    own = client is None
    http = client or httpx.Client(timeout=20.0, headers=_HEADERS)
    try:
        resp = http.get(_SURVEY_URL, params={"code": em_code})
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return empty
    finally:
        if own:
            http.close()
    if not isinstance(payload, dict):
        return empty
    return profile_from_survey_payload(payload)
