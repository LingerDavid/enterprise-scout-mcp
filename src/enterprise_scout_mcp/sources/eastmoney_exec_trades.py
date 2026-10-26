"""East Money F10 高管持股变动 (CompanyManagement.cgbd)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import exec_holding_change_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def _finite(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return str(value).strip()


def exec_trades_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    items = payload.get("cgbd") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items[: max(0, limit)]:
        if not isinstance(item, dict):
            continue
        person = str(item.get("EXECUTIVE_NAME") or item.get("HOLDER_NAME") or "").strip()
        as_of = date_str(item.get("END_DATE"))
        if not person or not as_of:
            continue
        out.append(
            exec_holding_change_row(
                security_id=security_id,
                as_of=as_of,
                person_name=person,
                position=str(item.get("POSITION") or "").strip(),
                change_shares=_finite(item.get("CHANGE_NUM")),
                avg_price=_finite(item.get("AVERAGE_PRICE")),
                shares_after=_finite(item.get("CHANGE_AFTER_HOLDNUM")),
                trade_way=str(item.get("TRADE_WAY") or "").strip(),
                holder_name=str(item.get("HOLDER_NAME") or "").strip(),
                document_id=document_id or f"eastmoney:f10:cgbd:{security_id}:{as_of}:{person}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_exec_holding_changes(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"exec_holding_changes": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("CompanyManagement", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    rows = exec_trades_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
        limit=limit,
    )
    return {
        "security_id": security_id,
        "exec_holding_changes": rows,
        "skipped": [] if rows else ["empty_cgbd"],
    }
