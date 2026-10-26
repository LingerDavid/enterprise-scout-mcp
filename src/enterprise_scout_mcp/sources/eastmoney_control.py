"""East Money F10 实际控制人 (ShareholderResearch.sjkzr)."""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import listed_control_row
from enterprise_scout_mcp.sources.eastmoney_common import em_code, fetch_f10_page


def control_from_f10_payload(
    payload: dict[str, Any],
    *,
    issuer_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    """Map ``sjkzr`` actual-controller block into listed_control hop 0."""
    items = payload.get("sjkzr") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return []
    row = items[0]
    if not isinstance(row, dict):
        return []
    name = str(row.get("HOLDER_NAME") or "").strip()
    if not name:
        return []
    ratio = row.get("HOLD_RATIO")
    ratio_s = ""
    if ratio is not None and ratio != "":
        try:
            ratio_s = str(float(ratio))
        except (TypeError, ValueError):
            ratio_s = str(ratio).strip()
    return [
        listed_control_row(
            issuer_id=issuer_id,
            as_of=collected_at[:10] if collected_at else "",
            hop="0",
            src_name=name,
            dst_name="",
            ratio=ratio_s,
            ratio_kind="voting",
            is_concert_party="false",
            endpoint_type="natural",
            document_id=document_id or f"eastmoney:f10:sjkzr:{issuer_id}",
            collected_at=collected_at,
        )
    ]


def fetch_actual_controller(
    symbol_or_security: str,
    *,
    issuer_id: str = "",
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"control": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    issuer = str(issuer_id or security_id).strip()
    payload = fetch_f10_page("ShareholderResearch", symbol_or_security, client=client)
    rows = control_from_f10_payload(
        payload,
        issuer_id=issuer,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "issuer_id": issuer,
        "control": rows,
        "skipped": [] if rows else ["empty_sjkzr"],
    }
