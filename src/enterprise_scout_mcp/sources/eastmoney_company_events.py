"""East Money F10 公司大事 (CompanyBigNews PageAjax)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import company_event_row
from enterprise_scout_mcp.sources.eastmoney_common import em_code, fetch_f10_page


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def company_events_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    block = payload.get("dstx") if isinstance(payload, dict) else None
    if not isinstance(block, dict):
        return []
    groups = block.get("data")
    if not isinstance(groups, list):
        return []
    out: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for raw in group:
            if not isinstance(raw, dict):
                continue
            content = _str(raw.get("LEVEL1_CONTENT") or raw.get("LEVEL2_CONTENT"))
            event_date = _str(raw.get("NOTICE_DATE"))
            if not content and not event_date:
                continue
            info_code = _str(raw.get("INFO_CODE"))
            out.append(
                company_event_row(
                    security_id=security_id,
                    event_date=event_date,
                    event_type=_str(raw.get("EVENT_TYPE")),
                    specific_type=_str(raw.get("SPECIFIC_EVENTTYPE")),
                    content=content,
                    info_code=info_code,
                    document_id=document_id or f"eastmoney:f10:dstx:{security_id}:{info_code or event_date}",
                    collected_at=collected_at,
                )
            )
    return out


def fetch_company_events(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"company_events": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    payload = fetch_f10_page("CompanyBigNews", symbol_or_security, client=client)
    rows = company_events_from_payload(
        payload, security_id=security_id, document_id=document_id, collected_at=collected_at
    )
    return {
        "security_id": security_id,
        "company_events": rows,
        "skipped": [] if rows else ["empty_dstx"],
    }
