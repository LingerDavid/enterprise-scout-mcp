"""East Money F10 公司大事 (CompanyBigNews PageAjax)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import company_event_block_row, company_event_row
from enterprise_scout_mcp.sources.eastmoney_common import date_str, em_code, fetch_f10_page

_EVENT_BLOCK_SPECS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("gqzy", "pledge", "NOTICE_DATE", ("HOLDER_NAME", "PF_ORG")),
    ("dwdb", "guarantee", "NOTICE_DATE", ("GUAR_NAME", "GUARANTEED_NAME")),
    ("dzjy", "block_trade", "TRADE_DATE", ("BUYER_NAME", "SELLER_NAME")),
    ("lhbd", "dragon_tiger", "TRADE_DATE", ("EXPLANATION",)),
    ("rzrq", "margin", "TRADE_DATE", ("SECURITY_NAME_ABBR",)),
    ("wgcl", "violation", "NOTICE_DATE", ("PUNISH_OBJECT", "VIOLATE_TYPE")),
    ("ggcgbd", "exec_share_change", "CHANGE_DATE", ("PERSON_NAME", "CHANGE_REASON")),
)

_METRICS_SKIP = frozenset(
    {
        "SECUCODE",
        "SECURITY_CODE",
        "SECURITY_NAME_ABBR",
        "SECURITY_INNER_CODE",
        "SECURITY_TYPE",
        "SECURITY_TYPE_WEB",
        "ORG_CODE",
        "DERIVE_SECURITY_CODE",
        "SECURITY_NAME",
    }
)


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _headline(raw: dict[str, Any], fields: tuple[str, ...]) -> str:
    parts = [_str(raw.get(name)) for name in fields]
    parts = [p for p in parts if p]
    return " / ".join(parts)


def _metrics_blob(raw: dict[str, Any], *, skip: frozenset[str] = _METRICS_SKIP) -> str:
    metrics = {k: v for k, v in raw.items() if k not in skip and v is not None and v != ""}
    return json.dumps(metrics, ensure_ascii=False, sort_keys=True)


def company_events_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    block = payload.get("dstx") if isinstance(payload, dict) else None
    if not isinstance(block, dict):
        return []
    groups = block.get("data")
    if not isinstance(groups, list):
        return []
    out: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for raw in group:
            if not isinstance(raw, dict):
                continue
            content = _str(raw.get("LEVEL1_CONTENT") or raw.get("LEVEL2_CONTENT"))
            event_date = _str(raw.get("NOTICE_DATE"))
            if not content and not event_date:
                continue
            info_code = _str(raw.get("INFO_CODE"))
            out.append(
                company_event_row(
                    security_id=security_id,
                    event_date=event_date,
                    event_type=_str(raw.get("EVENT_TYPE")),
                    specific_type=_str(raw.get("SPECIFIC_EVENTTYPE")),
                    content=content,
                    info_code=info_code,
                    document_id=document_id or f"eastmoney:f10:dstx:{security_id}:{info_code or event_date}",
                    collected_at=collected_at,
                )
            )
    return out


def company_event_blocks_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    out: list[dict[str, Any]] = []
    for key, kind, date_field, headline_fields in _EVENT_BLOCK_SPECS:
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for idx, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            event_date = date_str(raw.get(date_field))
            headline = _headline(raw, headline_fields)
            if not event_date and not headline:
                continue
            dedupe = _str(raw.get("INFO_CODE") or raw.get("HOLDER_NAME") or raw.get("PERSON_NAME") or idx)
            out.append(
                company_event_block_row(
                    security_id=security_id,
                    block_kind=kind,
                    event_date=event_date,
                    headline=headline or kind,
                    metrics_json=_metrics_blob(raw),
                    document_id=document_id or f"eastmoney:f10:{key}:{security_id}:{event_date}:{dedupe}",
                    collected_at=collected_at,
                )
            )
    return out


def fetch_company_events(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {
            "company_events": [],
            "company_event_blocks": [],
            "skipped": ["unresolved_symbol"],
        }
    _em, security_id = parsed
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    payload = fetch_f10_page("CompanyBigNews", symbol_or_security, client=client)
    events = company_events_from_payload(
        payload, security_id=security_id, document_id=document_id, collected_at=collected_at
    )
    blocks = company_event_blocks_from_payload(
        payload, security_id=security_id, document_id=document_id, collected_at=collected_at
    )
    skipped: list[str] = []
    if not events:
        skipped.append("empty_dstx")
    if not blocks:
        skipped.append("empty_event_blocks")
    return {
        "security_id": security_id,
        "company_events": events,
        "company_event_blocks": blocks,
        "skipped": skipped,
    }
