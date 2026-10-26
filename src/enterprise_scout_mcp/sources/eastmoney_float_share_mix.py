"""East Money F10 流通股份构成 (ShareholderResearch.ltgf)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import float_share_mix_row
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


def float_share_mix_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("ltgf") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return []
    row = items[0]
    if not isinstance(row, dict):
        return []
    as_of = date_str(row.get("END_DATE"))
    if not as_of:
        return []
    return [
        float_share_mix_row(
            security_id=security_id,
            as_of=as_of,
            limited_shares=_int_str(row.get("LIMITED_SHARES")),
            unlimited_shares=_int_str(row.get("OTHER_UNLIMITED_SHARES")),
            other_unlimited_shares=_int_str(row.get("OTHER_UNLIMITED_SHARES")),
            hold_num_count=_int_str(row.get("HOLD_NUM_COUNT")),
            limited_pct=_finite(row.get("LIMITED_SHARES_RATIO")),
            unlimited_pct=_finite(row.get("UNLIMITED_SHARES_RATIO")),
            document_id=document_id or f"eastmoney:f10:ltgf:{security_id}:{as_of}",
            collected_at=collected_at,
        )
    ]


def fetch_float_share_mix(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"float_share_mix": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("ShareholderResearch", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    rows = float_share_mix_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "float_share_mix": rows,
        "skipped": [] if rows else ["empty_ltgf"],
    }
