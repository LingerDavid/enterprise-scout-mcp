"""East Money F10 股东人数 (ShareholderResearch.gdrs) → listed/holder_stats."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import holder_stats_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def holder_stats_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("gdrs") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        as_of = date_str(item.get("END_DATE"))
        count = item.get("HOLDER_TOTAL_NUM")
        if not as_of or count is None:
            continue
        out.append(
            holder_stats_row(
                security_id=security_id,
                as_of=as_of,
                holder_count=str(int(float(count))),
                holder_count_change_pct=_finite(item.get("TOTAL_NUM_RATIO")),
                avg_free_shares=_finite(item.get("AVG_FREE_SHARES")),
                avg_hold_amt=_finite(item.get("AVG_HOLD_AMT")),
                document_id=document_id or f"eastmoney:f10:gdrs:{security_id}:{as_of}",
                collected_at=collected_at,
            )
        )
    return out


def _finite(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return str(value).strip()


def fetch_holder_stats(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"holder_stats": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("ShareholderResearch", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    rows = holder_stats_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "holder_stats": rows,
        "skipped": [] if rows else ["empty_gdrs"],
    }
