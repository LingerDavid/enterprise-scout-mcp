"""East Money F10 分红融资 → listed/dividends rows."""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import dividends_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def dividends_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    """Map ``fhyx`` dividend history into warehouse rows."""
    items = payload.get("fhyx") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        notice = date_str(item.get("NOTICE_DATE"))
        if not notice:
            continue
        plan = str(item.get("IMPL_PLAN_PROFILE") or "").strip()
        out.append(
            dividends_row(
                security_id=security_id,
                notice_date=notice,
                ex_dividend_date=date_str(item.get("EX_DIVIDEND_DATE")),
                pay_cash_date=date_str(item.get("PAY_CASH_DATE")),
                record_date=date_str(item.get("EQUITY_RECORD_DATE")),
                assign_progress=str(item.get("ASSIGN_PROGRESS") or "").strip(),
                impl_plan=plan,
                document_id=document_id or f"eastmoney:f10:fhyx:{security_id}:{notice}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_dividends(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"dividends": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("BonusFinancing", symbol_or_security, client=client)
    rows = dividends_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "dividends": rows,
        "skipped": [] if rows else ["empty_fhyx"],
    }
