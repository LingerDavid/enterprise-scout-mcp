"""East Money F10 机构持股 (ShareholderResearch.jgcc)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import institutional_holding_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def _finite(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return str(value).strip()


def institutional_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("jgcc") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        org_type = str(item.get("ORG_TYPE") or "").strip()
        as_of = date_str(item.get("REPORT_DATE"))
        if not org_type or not as_of:
            continue
        org_count = item.get("TOTAL_ORG_NUM")
        out.append(
            institutional_holding_row(
                security_id=security_id,
                as_of=as_of,
                org_type=org_type,
                org_count="" if org_count is None else str(int(float(org_count))),
                total_free_shares=_finite(item.get("TOTAL_FREE_SHARES")),
                pct_float=_finite(item.get("TOTAL_SHARES_RATIO")),
                pct_total=_finite(item.get("ALL_SHARES_RATIO")),
                document_id=document_id or f"eastmoney:f10:jgcc:{security_id}:{as_of}:{org_type}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_institutional_holdings(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"institutional_holdings": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("ShareholderResearch", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    rows = institutional_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "institutional_holdings": rows,
        "skipped": [] if rows else ["empty_jgcc"],
    }
