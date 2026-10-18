"""East Money F10 top-10 holders → listed holders rows.

Not a substitute for the securities register in the annual report PDF.
Used as a sample feed until PDF extraction lands.
"""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.output.listed_schema import holders_row
from enterprise_scout_mcp.sources.cninfo import resolve_listing

_F10_URL = "https://emweb.securities.eastmoney.com/PC_HSF10/ShareholderResearch/PageAjax"
_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://emweb.securities.eastmoney.com/",
    "User-Agent": "Mozilla/5.0",
}


def _em_code(symbol_or_security: str) -> tuple[str, str] | None:
    listing = resolve_listing(symbol_or_security)
    if listing is None:
        return None
    security_id, code, _column = listing
    exchange = security_id.split(":", 1)[0]
    prefix = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}.get(exchange, "")
    if not prefix:
        return None
    return f"{prefix}{code}", security_id


def _finite(v: Any) -> str:
    try:
        if v is None or v == "":
            return ""
        return str(float(v))
    except (TypeError, ValueError):
        return ""


def _date_str(v: Any) -> str:
    s = str(v or "").strip()
    return s[:10] if len(s) >= 10 else s


def holders_from_f10_payload(
    payload: dict[str, Any],
    *,
    security_id: str,
    document_id: str = "",
    collected_at: str = "",
) -> list[dict[str, Any]]:
    """Map Eastmoney ``sdgd`` list into warehouse holders rows."""
    items = payload.get("sdgd") if isinstance(payload, dict) else None
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
        ratio = item.get("HOLD_NUM_RATIO")
        as_of = _date_str(item.get("END_DATE"))
        out.append(
            holders_row(
                security_id=security_id,
                as_of=as_of,
                rank="" if rank is None else str(int(float(rank))),
                holder_name=name,
                holder_type=str(item.get("HOLDER_TYPE") or "").strip(),
                shares="" if shares is None else str(int(float(shares))),
                pct_total=_finite(ratio),
                share_class=str(item.get("SHARES_TYPE") or "").strip(),
                pledge_pct_of_holding="",
                pledge_as_of="",
                freeze_flag="",
                document_id=document_id or f"eastmoney-f10:{security_id}:{as_of}",
                collected_at=collected_at,
            )
        )
    return out


def fetch_top_holders(
    symbol_or_security: str,
    *,
    document_id: str = "",
    collected_at: str = "",
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Live F10 pull. Soft-fail → []."""
    parsed = _em_code(symbol_or_security)
    if parsed is None:
        return []
    em_code, security_id = parsed
    own = client is None
    http = client or httpx.Client(timeout=20.0, headers=_HEADERS)
    try:
        resp = http.get(_F10_URL, params={"code": em_code})
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return []
    finally:
        if own:
            http.close()
    if not isinstance(payload, dict):
        return []
    return holders_from_f10_payload(
        payload,
        security_id=security_id,
        document_id=document_id,
        collected_at=collected_at,
    )
