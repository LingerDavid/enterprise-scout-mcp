"""Assemble East-Money-style F10 dossier from EnterpriseLake listed tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from enterprise_scout_mcp.integrations.listed_peers import peer_compare
from enterprise_scout_mcp.output.listed_schema import to_tradecraft_symbol
from enterprise_scout_mcp.output.listed_writer import listed_part_path
from enterprise_scout_mcp.sources.cninfo import resolve_listing


def _read_table(warehouse_dir: Path, table: str) -> list[dict[str, Any]]:
    path = listed_part_path(warehouse_dir, table)
    if not path.is_file():
        return []
    try:
        import pyarrow.parquet as pq

        return pq.read_table(path).to_pylist()
    except Exception:
        return []


def _filter_security(rows: list[dict[str, Any]], security_id: str) -> list[dict[str, Any]]:
    return [r for r in rows if str(r.get("security_id") or "") == security_id]


def _filter_issuer(rows: list[dict[str, Any]], issuer_id: str) -> list[dict[str, Any]]:
    return [r for r in rows if str(r.get("issuer_id") or "") == issuer_id]


def _latest_period(facts: list[dict[str, Any]], issuer_id: str) -> str:
    periods = sorted(
        {
            str(r.get("period") or "")
            for r in facts
            if str(r.get("issuer_id") or "") == issuer_id and str(r.get("period") or "").isdigit()
        }
    )
    return periods[-1] if periods else ""


def build_listed_dossier(
    warehouse_dir: Path,
    symbol_or_security: str,
    *,
    include_peers: bool = True,
) -> dict[str, Any]:
    """Return tabbed dossier: 概况/股东/经营/员工竞争力/财务/分红/股本/高管/控制/同行."""
    warehouse_dir = Path(warehouse_dir)
    listing = resolve_listing(symbol_or_security)
    if listing is None:
        return {"ok": False, "skipped": ["unresolved_symbol"]}

    security_id, code, _column = listing
    identity_rows = _read_table(warehouse_dir, "identity")
    identity = next((r for r in identity_rows if str(r.get("security_id") or "") == security_id), None)
    if identity is None:
        return {"ok": False, "security_id": security_id, "skipped": ["no_identity"]}

    issuer_id = str(identity.get("issuer_id") or security_id)
    facts_all = _read_table(warehouse_dir, "facts")
    period = _latest_period(facts_all, issuer_id)
    facts = [r for r in facts_all if str(r.get("issuer_id") or "") == issuer_id and (not period or str(r.get("period") or "") == period)]

    dossier: dict[str, Any] = {
        "ok": True,
        "security_id": security_id,
        "symbol": to_tradecraft_symbol(security_id) or "",
        "issuer_id": issuer_id,
        "tabs": {
            "公司概况": identity,
            "股东研究": {
                "holders": _filter_security(_read_table(warehouse_dir, "holders"), security_id),
                "control": _filter_issuer(_read_table(warehouse_dir, "listed_control"), issuer_id),
            },
            "经营分析": {
                "segments": _filter_issuer(_read_table(warehouse_dir, "segments"), issuer_id),
            },
            "员工及业务竞争力": {
                "workforce": sorted(
                    _filter_issuer(_read_table(warehouse_dir, "workforce"), issuer_id),
                    key=lambda r: str(r.get("period") or ""),
                    reverse=True,
                ),
                "education": _filter_issuer(
                    _read_table(warehouse_dir, "workforce_education"),
                    issuer_id,
                ),
            },
            "财务分析": {
                "period": period,
                "facts": facts,
            },
            "分红融资": {
                "dividends": _filter_security(_read_table(warehouse_dir, "dividends"), security_id),
            },
            "股本结构": {
                "capital": _filter_security(_read_table(warehouse_dir, "capital"), security_id),
            },
            "公司高管": {
                "executives": _filter_security(_read_table(warehouse_dir, "executives"), security_id),
            },
            "子公司": {
                "subsidiaries": _filter_issuer(_read_table(warehouse_dir, "subsidiaries"), issuer_id),
            },
        },
    }
    if include_peers:
        dossier["tabs"]["同行比较"] = peer_compare(warehouse_dir, symbol_or_security, period=period)
    return dossier
