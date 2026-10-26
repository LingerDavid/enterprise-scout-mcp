"""East Money F10 发行信息 (CompanySurvey.fxxg) → listed/ipo_profile."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import ipo_profile_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def ipo_profile_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("fxxg") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return []
    row = items[0]
    if not isinstance(row, dict):
        return []
    listing_date = date_str(row.get("LISTING_DATE"))
    if not listing_date:
        return []
    return [
        ipo_profile_row(
            security_id=security_id,
            found_date=date_str(row.get("FOUND_DATE")),
            listing_date=listing_date,
            issue_price=_finite(row.get("ISSUE_PRICE")),
            total_issue_num=_finite(row.get("TOTAL_ISSUE_NUM")),
            par_value=_finite(row.get("PAR_VALUE")),
            issue_way=str(row.get("ISSUE_WAY") or "").strip(),
            document_id=document_id or f"eastmoney:f10:fxxg:{security_id}",
            collected_at=collected_at,
        )
    ]


def _finite(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return str(value).strip()


def fetch_ipo_profile(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"ipo_profile": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("CompanySurvey", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    rows = ipo_profile_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "ipo_profile": rows,
        "skipped": [] if rows else ["empty_fxxg"],
    }
