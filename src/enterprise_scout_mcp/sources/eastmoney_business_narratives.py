"""East Money F10 经营分析 narrative blocks (zyfw / jyps)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import business_review_row, business_scope_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page


def business_scope_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("zyfw") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return []
    row = items[0]
    if not isinstance(row, dict):
        return []
    scope = str(row.get("BUSINESS_SCOPE") or "").strip()
    if not scope:
        return []
    return [
        business_scope_row(
            security_id=security_id,
            business_scope=scope,
            document_id=document_id or f"eastmoney:f10:zyfw:{security_id}",
            collected_at=collected_at,
        )
    ]


def business_review_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("jyps") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return []
    # Prefer latest report_date when multiple snapshots exist.
    dated: list[tuple[str, dict[str, Any]]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        content = str(raw.get("BUSINESS_REVIEW") or "").strip()
        if not content:
            continue
        as_of = date_str(raw.get("REPORT_DATE"))
        dated.append((as_of, raw))
    if not dated:
        return []
    dated.sort(key=lambda pair: pair[0])
    as_of, row = dated[-1]
    content = str(row.get("BUSINESS_REVIEW") or "").strip()
    doc = document_id or f"eastmoney:f10:jyps:{security_id}:{as_of or 'latest'}"
    return [
        business_review_row(
            security_id=security_id,
            as_of=as_of,
            content=content,
            document_id=doc,
            collected_at=collected_at,
        )
    ]


def fetch_business_narratives(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Pull 主营范围 (zyfw) and 经营评述 (jyps) from BusinessAnalysis PageAjax."""
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {
            "business_scope": [],
            "business_review": [],
            "skipped": ["unresolved_symbol"],
        }
    _em, security_id = parsed
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    payload = fetch_f10_page("BusinessAnalysis", symbol_or_security, client=client)
    scope = business_scope_from_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    review = business_review_from_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    skipped: list[str] = []
    if not scope:
        skipped.append("empty_zyfw")
    if not review:
        skipped.append("empty_jyps")
    return {
        "security_id": security_id,
        "business_scope": scope,
        "business_review": review,
        "skipped": skipped,
    }
