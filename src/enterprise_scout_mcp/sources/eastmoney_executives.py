"""East Money F10 公司高管 → listed/executives rows."""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import executives_row
from enterprise_scout_mcp.sources.eastmoney_common import em_code, fetch_f10_page


def _str_int(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value).strip()


def executives_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    """Map ``gglb`` management list into warehouse rows."""
    items = payload.get("gglb") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("PERSON_NAME") or "").strip()
        if not name:
            continue
        out.append(
            executives_row(
                security_id=security_id,
                person_name=name,
                position=str(item.get("POSITION") or "").strip(),
                position_type=str(item.get("POSITION_TYPE_CODE") or "").strip(),
                sex=str(item.get("SEX") or "").strip(),
                age=_str_int(item.get("AGE")),
                education=str(item.get("HIGH_DEGREE") or "").strip(),
                salary=_str_int(item.get("SALARY")),
                shares=_str_int(item.get("HOLD_NUM")),
                resume=str(item.get("RESUME") or "").strip()[:2000],
                incumbent_since=str(item.get("INCUMBENT_TIME") or "").strip(),
                document_id=document_id or f"eastmoney:f10:gglb:{security_id}:{name}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_executives(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"executives": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    payload = fetch_f10_page("CompanyManagement", symbol_or_security, client=client)
    rows = executives_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "executives": rows,
        "skipped": [] if rows else ["empty_gglb"],
    }
