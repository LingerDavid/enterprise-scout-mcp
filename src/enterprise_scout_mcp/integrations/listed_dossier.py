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
    identity_matches = [r for r in identity_rows if str(r.get("security_id") or "") == security_id]
    identity = (
        max(identity_matches, key=lambda r: str(r.get("collected_at") or ""))
        if identity_matches
        else None
    )
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
            "公司概况": {
                **identity,
                "profile": _filter_security(_read_table(warehouse_dir, "company_profile"), security_id),
                "ipo_profile": _filter_security(_read_table(warehouse_dir, "ipo_profile"), security_id),
            },
            "股东研究": {
                "holders": _filter_security(_read_table(warehouse_dir, "holders"), security_id),
                "float_holders": _filter_security(_read_table(warehouse_dir, "float_holders"), security_id),
                "institutional_holdings": sorted(
                    _filter_security(_read_table(warehouse_dir, "institutional_holdings"), security_id),
                    key=lambda r: str(r.get("as_of") or ""),
                    reverse=True,
                ),
                "fund_holdings": sorted(
                    _filter_security(_read_table(warehouse_dir, "fund_holdings"), security_id),
                    key=lambda r: str(r.get("as_of") or ""),
                    reverse=True,
                ),
                "holder_stats": sorted(
                    _filter_security(_read_table(warehouse_dir, "holder_stats"), security_id),
                    key=lambda r: str(r.get("as_of") or ""),
                    reverse=True,
                ),
                "control": _filter_issuer(_read_table(warehouse_dir, "listed_control"), issuer_id),
                "float_share_mix": _filter_security(_read_table(warehouse_dir, "float_share_mix"), security_id),
            },
            "经营分析": {
                "business_scope": _filter_security(
                    _read_table(warehouse_dir, "business_scope"),
                    security_id,
                ),
                "segments": _filter_issuer(_read_table(warehouse_dir, "segments"), issuer_id),
                "business_review": _filter_security(
                    _read_table(warehouse_dir, "business_review"),
                    security_id,
                ),
            },
            "核心题材": {
                "highlights": _filter_security(
                    _read_table(warehouse_dir, "core_highlights"),
                    security_id,
                ),
                "concept_boards": sorted(
                    _filter_security(_read_table(warehouse_dir, "concept_boards"), security_id),
                    key=lambda r: int(str(r.get("board_rank") or "0") or 0),
                ),
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
            "分红融资": _dividend_financing_tab(warehouse_dir, security_id),
            "盈利预测": {
                "ratings": _filter_security(
                    _read_table(warehouse_dir, "forecast_ratings"),
                    security_id,
                ),
                "estimates": sorted(
                    _filter_security(_read_table(warehouse_dir, "forecast_estimates"), security_id),
                    key=lambda r: (str(r.get("year") or ""), str(r.get("org_name") or "")),
                ),
            },
            "公司大事": {
                "events": sorted(
                    _filter_security(_read_table(warehouse_dir, "company_events"), security_id),
                    key=lambda r: str(r.get("event_date") or ""),
                    reverse=True,
                ),
            },
            "股本结构": {
                "capital": _filter_security(_read_table(warehouse_dir, "capital"), security_id),
                "capital_history": sorted(
                    _filter_security(_read_table(warehouse_dir, "capital_history"), security_id),
                    key=lambda r: str(r.get("as_of") or ""),
                    reverse=True,
                ),
                "restricted_unlock": sorted(
                    _filter_security(_read_table(warehouse_dir, "restricted_unlock"), security_id),
                    key=lambda r: str(r.get("lift_date") or ""),
                    reverse=True,
                ),
            },
            "公司高管": {
                "executives": _filter_security(_read_table(warehouse_dir, "executives"), security_id),
                "holding_changes": sorted(
                    _filter_security(_read_table(warehouse_dir, "exec_holding_changes"), security_id),
                    key=lambda r: str(r.get("as_of") or ""),
                    reverse=True,
                ),
            },
            "子公司": {
                "subsidiaries": _filter_issuer(_read_table(warehouse_dir, "subsidiaries"), issuer_id),
            },
        },
    }
    if include_peers:
        em_peers = _filter_security(_read_table(warehouse_dir, "peer_compare_em"), security_id)
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for row in em_peers:
            by_kind.setdefault(str(row.get("compare_kind") or ""), []).append(row)
        dossier["tabs"]["同行比较"] = {
            "warehouse_percentile": peer_compare(warehouse_dir, symbol_or_security, period=period),
            "growth": by_kind.get("growth", []),
            "valuation": by_kind.get("valuation", []),
            "dupont": by_kind.get("dupont", []),
            "market": by_kind.get("market", []),
            "scale": by_kind.get("scale", []),
        }
    return dossier


def _dividend_financing_tab(warehouse_dir: Path, security_id: str) -> dict[str, Any]:
    summary = sorted(
        _filter_security(_read_table(warehouse_dir, "dividend_summary"), security_id),
        key=lambda r: str(r.get("year") or ""),
        reverse=True,
    )
    overview: dict[str, Any] = {}
    if summary:
        try:
            total_div = sum(float(r.get("total_dividend") or 0) for r in summary)
            total_seo = sum(int(float(r.get("seo_count") or 0)) for r in summary)
            overview = {
                "dividend_years": len(summary),
                "total_dividend": str(total_div),
                "total_seo_count": str(total_seo),
            }
        except (TypeError, ValueError):
            overview = {"dividend_years": len(summary)}
    return {
        "overview": overview,
        "dividends": _filter_security(_read_table(warehouse_dir, "dividends"), security_id),
        "dividend_summary": summary,
        "seo_issues": sorted(
            _filter_security(_read_table(warehouse_dir, "seo_issues"), security_id),
            key=lambda r: str(r.get("notice_date") or ""),
            reverse=True,
        ),
        "allotment_issues": sorted(
            _filter_security(_read_table(warehouse_dir, "allotment_issues"), security_id),
            key=lambda r: str(r.get("notice_date") or ""),
            reverse=True,
        ),
    }
