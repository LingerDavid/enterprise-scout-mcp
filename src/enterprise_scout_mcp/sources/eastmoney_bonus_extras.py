"""East Money F10 分红融资扩展: lnfhrz (分红统计) / zfmx (增发) / pgmx (配股)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import dividend_summary_row, seo_issue_row
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


def dividend_summary_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("lnfhrz") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        year = str(item.get("STATISTICS_YEAR") or "").strip()
        if not year:
            continue
        out.append(
            dividend_summary_row(
                security_id=security_id,
                year=year,
                total_dividend=_finite(item.get("TOTAL_DIVIDEND")),
                seo_count=_int_str(item.get("SEO_NUM")),
                allotment_count=_int_str(item.get("ALLOTMENT_NUM")),
                ipo_count=_int_str(item.get("IPO_NUM")),
                document_id=document_id or f"eastmoney:f10:lnfhrz:{security_id}:{year}",
                collected_at=collected_at,
            )
        )
    return out


def seo_issues_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("zfmx") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        notice = date_str(item.get("NOTICE_DATE"))
        if not notice:
            continue
        out.append(
            seo_issue_row(
                security_id=security_id,
                notice_date=notice,
                listing_date=date_str(item.get("LISTING_DATE")),
                issue_num=_int_str(item.get("ISSUE_NUM")),
                issue_price=_finite(item.get("ISSUE_PRICE")),
                net_raise_funds=_finite(item.get("NET_RAISE_FUNDS")),
                issue_way=str(item.get("ISSUE_WAY_EXPLAIN") or "").strip(),
                reg_date=date_str(item.get("REG_DATE")),
                receive_date=date_str(item.get("RECEIVE_DATE")),
                document_id=document_id or f"eastmoney:f10:zfmx:{security_id}:{notice}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_bonus_extras(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {
            "dividend_summary": [],
            "seo_issues": [],
            "skipped": ["unresolved_symbol"],
        }
    _em, security_id = parsed
    payload = fetch_f10_page("BonusFinancing", symbol_or_security, client=client)
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    summary = dividend_summary_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    seo = seo_issues_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    skipped: list[str] = []
    if not summary:
        skipped.append("empty_lnfhrz")
    if not seo:
        skipped.append("empty_zfmx")
    return {
        "security_id": security_id,
        "dividend_summary": summary,
        "seo_issues": seo,
        "skipped": skipped,
    }
