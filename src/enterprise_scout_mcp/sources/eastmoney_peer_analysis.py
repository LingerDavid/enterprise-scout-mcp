"""East Money F10 同行比较 (IndustryAnalysis PageAjax)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import peer_compare_em_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page

_PEER_BLOCKS: tuple[tuple[str, str], ...] = (
    ("czxbj", "growth"),
    ("gzbj", "valuation"),
    ("dbfxbj", "dupont"),
    ("scbx", "market"),
    ("gsgm", "scale"),
)


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _metrics_blob(raw: dict[str, Any]) -> str:
    skip = {
        "SECUCODE",
        "SECURITY_CODE",
        "SECURITY_NAME_ABBR",
        "CORRE_SECUCODE",
        "CORRE_SECURITY_CODE",
        "CORRE_SECURITY_NAME",
        "CORRE_ORG_CODE",
        "ORG_CODE",
        "REPORT_DATE",
        "REPORT_TYPE",
    }
    metrics = {k: v for k, v in raw.items() if k not in skip and v is not None and v != ""}
    return json.dumps(metrics, ensure_ascii=False, sort_keys=True)


def peer_compare_rows_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    out: list[dict[str, Any]] = []
    for key, kind in _PEER_BLOCKS:
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for raw in items:
            if not isinstance(raw, dict):
                continue
            compare_name = _str(raw.get("CORRE_SECURITY_NAME") or raw.get("SECURITY_NAME_ABBR"))
            report_date = date_str(raw.get("REPORT_DATE") or raw.get("TRADE_DATE"))
            if not compare_name and not report_date:
                continue
            out.append(
                peer_compare_em_row(
                    security_id=security_id,
                    compare_kind=kind,
                    compare_name=compare_name or kind,
                    report_date=report_date,
                    metrics_json=_metrics_blob(raw),
                    document_id=document_id or f"eastmoney:f10:{key}:{security_id}:{compare_name}",
                    collected_at=collected_at,
                )
            )
    return out


def fetch_peer_analysis(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"peer_compare_em": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    payload = fetch_f10_page("IndustryAnalysis", symbol_or_security, client=client)
    rows = peer_compare_rows_from_payload(
        payload, security_id=security_id, document_id=document_id, collected_at=collected_at
    )
    return {
        "security_id": security_id,
        "peer_compare_em": rows,
        "skipped": [] if rows else ["empty_industry_analysis"],
    }
