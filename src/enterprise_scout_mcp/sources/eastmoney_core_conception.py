"""East Money F10 核心题材 (CoreConception: hxtc highlights + ssbk concept boards)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import concept_board_row, core_highlight_row
from enterprise_scout_mcp.sources.eastmoney_common import em_code, fetch_f10_page


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def core_highlights_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("hxtc") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        content = _str(raw.get("MAINPOINT_CONTENT"))
        if not content:
            continue
        rank = _str(raw.get("MAINPOINT"))
        keyword = _str(raw.get("KEYWORD"))
        out.append(
            core_highlight_row(
                security_id=security_id,
                keyword=keyword,
                key_classif=_str(raw.get("KEY_CLASSIF")),
                key_classif_code=_str(raw.get("KEY_CLASSIF_CODE")),
                mainpoint_rank=rank,
                content=content,
                is_highlight=_str(raw.get("IS_POINT")) or "0",
                document_id=document_id or f"eastmoney:f10:hxtc:{security_id}:{keyword or rank}",
                collected_at=collected_at,
            )
        )
    return out


def concept_boards_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("ssbk") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        name = _str(raw.get("BOARD_NAME"))
        code = _str(raw.get("BOARD_CODE"))
        if not name and not code:
            continue
        out.append(
            concept_board_row(
                security_id=security_id,
                board_code=code,
                board_name=name,
                board_rank=_str(raw.get("BOARD_RANK")),
                is_precise=_str(raw.get("IS_PRECISE")),
                document_id=document_id or f"eastmoney:f10:ssbk:{security_id}:{code or name}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_core_conception(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Pull 核心亮点 (hxtc) and 概念板块 (ssbk) from CoreConception PageAjax."""
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {
            "core_highlights": [],
            "concept_boards": [],
            "skipped": ["unresolved_symbol"],
        }
    _em, security_id = parsed
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    payload = fetch_f10_page("CoreConception", symbol_or_security, client=client)
    highlights = core_highlights_from_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    boards = concept_boards_from_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    skipped: list[str] = []
    if not highlights:
        skipped.append("empty_hxtc")
    if not boards:
        skipped.append("empty_ssbk")
    return {
        "security_id": security_id,
        "core_highlights": highlights,
        "concept_boards": boards,
        "skipped": skipped,
    }
