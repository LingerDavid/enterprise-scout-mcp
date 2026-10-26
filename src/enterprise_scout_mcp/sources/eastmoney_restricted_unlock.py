"""East Money F10 限售解禁 (CapitalStockStructure.xsjj)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import restricted_unlock_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def _finite(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return str(value).strip()


def _int_str(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return ""


def restricted_unlock_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("xsjj") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        lift_date = date_str(item.get("LIFT_DATE"))
        if not lift_date:
            continue
        out.append(
            restricted_unlock_row(
                security_id=security_id,
                lift_date=lift_date,
                lift_shares=_int_str(item.get("LIFT_NUM")),
                lift_type=str(item.get("LIFT_TYPE") or "").strip(),
                pct_total=_finite(item.get("TOTAL_SHARES_RATIO")),
                pct_float_a=_finite(item.get("UNLIMITED_A_SHARES_RATIO")),
                document_id=document_id or f"eastmoney:f10:xsjj:{security_id}:{lift_date}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_restricted_unlock(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"restricted_unlock": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("CapitalStockStructure", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    rows = restricted_unlock_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "restricted_unlock": rows,
        "skipped": [] if rows else ["empty_xsjj"],
    }
