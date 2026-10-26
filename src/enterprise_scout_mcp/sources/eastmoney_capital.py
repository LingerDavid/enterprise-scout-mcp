"""East Money F10 股本结构 → listed/capital rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import capital_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def capital_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    """Map ``gbjg`` (current structure) into capital rows."""
    items = payload.get("gbjg") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return []
    row = items[0]
    if not isinstance(row, dict):
        return []
    as_of = date_str(row.get("END_DATE")) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = row.get("TOTAL_SHARES")
    float_sh = row.get("UNLIMITED_SHARES") or row.get("LISTED_A_SHARES")
    limited = row.get("LIMITED_SHARES")
    listed_a = row.get("LISTED_A_SHARES")
    if total is None and float_sh is None:
        return []
    return [
        capital_row(
            security_id=security_id,
            as_of=as_of,
            total_shares="" if total is None else str(int(float(total))),
            float_shares="" if float_sh is None else str(int(float(float_sh))),
            limited_shares="" if limited is None else str(int(float(limited))),
            listed_a_shares="" if listed_a is None else str(int(float(listed_a))),
            document_id=document_id or f"eastmoney:f10:gbjg:{security_id}:{as_of}",
            collected_at=collected_at,
        )
    ]


def fetch_capital_structure(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Live F10 pull. Returns report dict with ``capital`` list."""
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"capital": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("CapitalStockStructure", symbol_or_security, client=client)
    if not payload:
        return {"capital": [], "skipped": ["empty_payload"], "security_id": security_id}
    rows = capital_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "capital": rows,
        "skipped": [] if rows else ["empty_gbjg"],
    }
