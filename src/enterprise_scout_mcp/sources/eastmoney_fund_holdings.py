"""East Money F10 基金持股 (ShareholderResearch.jjcq)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import fund_holding_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def _finite(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return str(value).strip()


def fund_holdings_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("jjcg") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("HOLDER_NAME") or "").strip()
        as_of = date_str(item.get("REPORT_DATE"))
        if not name or not as_of:
            continue
        shares = item.get("TOTAL_SHARES")
        out.append(
            fund_holding_row(
                security_id=security_id,
                as_of=as_of,
                fund_name=name,
                fund_code=str(item.get("FUND_CODE") or item.get("FUND_DERIVECODE") or "").strip(),
                org_type=str(item.get("ORG_TYPE") or "").strip(),
                shares="" if shares is None else str(int(float(shares))),
                hold_value=_finite(item.get("HOLD_VALUE")),
                pct_total=_finite(item.get("TOTALSHARES_RATIO")),
                pct_float=_finite(item.get("FREESHARES_RATIO")),
                netvalue_ratio=_finite(item.get("NETVALUE_RATIO")),
                document_id=document_id or f"eastmoney:f10:jjcg:{security_id}:{as_of}:{name}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_fund_holdings(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"fund_holdings": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("ShareholderResearch", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    rows = fund_holdings_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "fund_holdings": rows,
        "skipped": [] if rows else ["empty_jjcq"],
    }
