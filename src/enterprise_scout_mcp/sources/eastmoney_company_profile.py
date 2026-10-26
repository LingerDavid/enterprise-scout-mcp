"""East Money F10 CompanySurvey.jbzl → listed/company_profile."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import company_profile_row
from enterprise_scout_mcp.sources.eastmoney_common import em_code, fetch_f10_page


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _finite(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return _str(value)


def company_profile_from_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    items = payload.get("jbzl") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return []
    row = items[0]
    name = _str(row.get("ORG_NAME") or row.get("SECURITY_NAME_ABBR"))
    profile = _str(row.get("ORG_PROFILE"))
    if not name and not profile:
        return []
    return [
        company_profile_row(
            security_id=security_id,
            issuer_name=name,
            org_profile=profile,
            chairman=_str(row.get("CHAIRMAN")),
            president=_str(row.get("PRESIDENT")),
            secretary=_str(row.get("SECRETARY")),
            legal_person=_str(row.get("LEGAL_PERSON")),
            org_web=_str(row.get("ORG_WEB")),
            org_tel=_str(row.get("ORG_TEL")),
            org_email=_str(row.get("ORG_EMAIL")),
            office_address=_str(row.get("ADDRESS")),
            reg_address=_str(row.get("REG_ADDRESS")),
            reg_capital=_finite(row.get("REG_CAPITAL")),
            emp_num=_finite(row.get("EMP_NUM")),
            csrc_industry=_str(row.get("INDUSTRYCSRC1")),
            em_industry=_str(row.get("EM2016")),
            document_id=document_id or f"eastmoney:f10:jbzl:{security_id}",
            collected_at=collected_at,
        )
    ]


def fetch_company_profile(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    parsed = em_code(symbol_or_security)
    if parsed is None:
        return {"company_profile": [], "skipped": ["unresolved_symbol"]}
    _em, security_id = parsed
    if not collected_at:
        collected_at = datetime.now(timezone.utc).isoformat()
    payload = fetch_f10_page("CompanySurvey", symbol_or_security, client=client)
    rows = company_profile_from_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
    return {
        "security_id": security_id,
        "company_profile": rows,
        "skipped": [] if rows else ["empty_jbzl"],
    }
