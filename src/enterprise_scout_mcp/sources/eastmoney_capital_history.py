"""East Money F10 股本变动历史: gbgc / lngbbd → listed/capital_history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import capital_history_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def _int_str(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return ""


def _merge_history_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("as_of") or "")
        if not key:
            continue
        slot = merged.setdefault(key, row)
        for field, value in row.items():
            if value not in ("", None) and slot.get(field) in ("", None):
                slot[field] = value
    return sorted(merged.values(), key=lambda r: str(r.get("as_of") or ""), reverse=True)


def capital_history_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gbgc = payload.get("gbgc") if isinstance(payload, dict) else None
    if isinstance(gbgc, list):
        for item in gbgc:
            if not isinstance(item, dict):
                continue
            as_of = date_str(item.get("END_DATE"))
            if not as_of:
                continue
            rows.append(
                capital_history_row(
                    security_id=security_id,
                    as_of=as_of,
                    total_shares=_int_str(item.get("TOTAL_SHARES")),
                    listed_a_shares=_int_str(item.get("LISTED_A_SHARES")),
                    limited_shares=_int_str(item.get("LIMITED_SHARES")),
                    unlimited_shares="",
                    lock_shares="",
                    change_reason="",
                    document_id=document_id or f"eastmoney:f10:gbgc:{security_id}:{as_of}",
                    collected_at=collected_at,
                )
            )
    lngbbd = payload.get("lngbbd") if isinstance(payload, dict) else None
    if isinstance(lngbbd, list):
        for item in lngbbd:
            if not isinstance(item, dict):
                continue
            as_of = date_str(item.get("END_DATE"))
            if not as_of:
                continue
            rows.append(
                capital_history_row(
                    security_id=security_id,
                    as_of=as_of,
                    total_shares=_int_str(item.get("TOTAL_SHARES")),
                    listed_a_shares=_int_str(item.get("LISTED_A_SHARES")),
                    limited_shares=_int_str(item.get("LIMITED_SHARES")),
                    unlimited_shares=_int_str(item.get("UNLIMITED_SHARES")),
                    lock_shares=_int_str(item.get("LOCK_SHARES")),
                    change_reason=str(item.get("CHANGE_REASON") or "").strip(),
                    document_id=document_id or f"eastmoney:f10:lngbbd:{security_id}:{as_of}",
                    collected_at=collected_at,
                )
            )
    return _merge_history_rows(rows)


def fetch_capital_history(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"capital_history": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("CapitalStockStructure", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    rows = capital_history_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "capital_history": rows,
        "skipped": [] if rows else ["empty_gbgc_lngbbd"],
    }
