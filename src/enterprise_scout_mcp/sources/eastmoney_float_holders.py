"""East Money F10 十大流通股东 (ShareholderResearch.sdltgd)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import float_holders_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def _finite(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return str(value).strip()


def float_holders_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("sdltgd") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("HOLDER_NAME") or "").strip()
        if not name:
            continue
        rank = item.get("HOLDER_RANK")
        shares = item.get("HOLD_NUM")
        as_of = date_str(item.get("END_DATE"))
        out.append(
            float_holders_row(
                security_id=security_id,
                as_of=as_of,
                rank="" if rank is None else str(int(float(rank))),
                holder_name=name,
                holder_type=str(item.get("HOLDER_TYPE") or "").strip(),
                shares="" if shares is None else str(int(float(shares))),
                pct_float=_finite(item.get("FREE_HOLDNUM_RATIO")),
                share_class=str(item.get("SHARES_TYPE") or "").strip(),
                change_shares=_finite(item.get("HOLD_NUM_CHANGE")),
                change_pct=_finite(item.get("CHANGE_RATIO")),
                document_id=document_id or f"eastmoney:f10:sdltgd:{security_id}:{as_of}:{name}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_float_holders(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"float_holders": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("ShareholderResearch", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    rows = float_holders_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "float_holders": rows,
        "skipped": [] if rows else ["empty_sdltgd"],
    }
