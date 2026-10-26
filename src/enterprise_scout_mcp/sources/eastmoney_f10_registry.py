"""East Money F10 tab registry — each板块 declares PageAjax / datacenter structure."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from enterprise_scout_mcp.sources.eastmoney_common import em_code
from enterprise_scout_mcp.sources.eastmoney_f10_probe import (
    new_f10_client,
    probe_datacenter_report,
    probe_page_ajax_module,
)


@dataclass(frozen=True)
class F10TabSpec:
    tab: str
    page_module: str | None = None
    mapped_page_keys: dict[str, str] = field(default_factory=dict)
    datacenter_reports: dict[str, str] = field(default_factory=dict)
    notes: str = ""


F10_TABS: tuple[F10TabSpec, ...] = (
    F10TabSpec(
        tab="公司概况",
        page_module="CompanySurvey",
        mapped_page_keys={"jbzl": "identity", "fxxg": "ipo_profile"},
    ),
    F10TabSpec(
        tab="股东研究",
        page_module="ShareholderResearch",
        mapped_page_keys={
            "sdgd": "holders",
            "sdltgd": "float_holders",
            "sjkzr": "listed_control",
            "gdrs": "holder_stats",
            "jgcc": "institutional_holdings",
            "jjcg": "fund_holdings",
            "ltgf": "float_share_mix",
        },
    ),
    F10TabSpec(
        tab="经营分析",
        page_module="BusinessAnalysis",
        mapped_page_keys={
            "zyfw": "business_scope",
            "zygcfx": "segments",
            "jyps": "business_review",
        },
    ),
    F10TabSpec(
        tab="核心题材",
        page_module="CoreConception",
        mapped_page_keys={
            "hxtc": "core_highlights",
            "ssbk": "concept_boards",
        },
        notes="hxtc=亮点/要点条目; ssbk=所属概念板块",
    ),
    F10TabSpec(
        tab="员工及业务竞争力",
        datacenter_reports={
            "RPT_F10_FINANCE_MAINFINADATA": "workforce",
            "RPT_F10_FINANCE_GCASHFLOW": "workforce.pay_staff_cash",
            "RPT_F10_FINANCE_GBALANCE": "workforce.staff_salary_payable",
        },
        notes="education mix via annual_pdf → listed/workforce_education when section present",
    ),
    F10TabSpec(
        tab="财务分析",
        datacenter_reports={
            "RPT_F10_FINANCE_GINCOME": "facts.income",
            "RPT_F10_FINANCE_GBALANCE": "facts.balance",
            "RPT_F10_FINANCE_GCASHFLOW": "facts.cash_flow",
        },
    ),
    F10TabSpec(
        tab="分红融资",
        page_module="BonusFinancing",
        mapped_page_keys={
            "fhyx": "dividends",
            "lnfhrz": "dividend_summary",
            "zfmx": "seo_issues",
            "pgmx": "allotment_issues",
        },
        notes="pgmx (配股) often empty per symbol",
    ),
    F10TabSpec(
        tab="股本结构",
        page_module="CapitalStockStructure",
        mapped_page_keys={
            "gbjg": "capital",
            "gbgc": "capital_history",
            "lngbbd": "capital_history",
            "xsjj": "restricted_unlock",
        },
        notes="xsjj (限售解禁) often empty per symbol",
    ),
    F10TabSpec(
        tab="公司高管",
        page_module="CompanyManagement",
        mapped_page_keys={"gglb": "executives", "cgbd": "exec_holding_changes"},
    ),
    F10TabSpec(
        tab="同行比较",
        notes="computed in-warehouse from listed/facts + identity",
    ),
)


def probe_f10_tab(
    spec: F10TabSpec,
    symbol_or_security: str,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Probe one F10 tab's live API structure for a symbol."""
    parsed = em_code(symbol_or_security)
    report: dict[str, Any] = {
        "tab": spec.tab,
        "input": symbol_or_security,
        "notes": spec.notes,
        "mapped_page_keys": dict(spec.mapped_page_keys),
        "datacenter_reports": dict(spec.datacenter_reports),
    }
    if parsed is None:
        report["skipped"] = ["unresolved_symbol"]
        return report
    em, security_id = parsed
    report["em_code"] = em
    report["security_id"] = security_id

    own = client is None
    http = client or new_f10_client()
    try:
        if spec.page_module:
            report["page_ajax"] = probe_page_ajax_module(
                spec.page_module,
                em,
                client=http,
                mapped_keys=spec.mapped_page_keys,
            )
        if spec.datacenter_reports:
            sym = symbol_or_security.strip().upper()
            if "." not in sym:
                from enterprise_scout_mcp.output.listed_schema import to_tradecraft_symbol

                sym = to_tradecraft_symbol(security_id) or sym
            dc: dict[str, Any] = {}
            for rn, target in spec.datacenter_reports.items():
                dc[rn] = {**probe_datacenter_report(rn, sym, client=http), "warehouse_target": target}
            report["datacenter"] = dc
    finally:
        if own:
            http.close()
    return report


def probe_all_f10_tabs(
    symbol_or_security: str,
    *,
    tabs: tuple[str, ...] | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Probe every registered tab (or a subset by Chinese tab name)."""
    selected = F10_TABS
    if tabs:
        want = set(tabs)
        selected = tuple(s for s in F10_TABS if s.tab in want)
    own = client is None
    http = client or new_f10_client()
    out: dict[str, Any] = {
        "input": symbol_or_security,
        "tabs": [],
    }
    try:
        for spec in selected:
            out["tabs"].append(probe_f10_tab(spec, symbol_or_security, client=http))
    finally:
        if own:
            http.close()
    out["ok"] = all(not t.get("skipped") for t in out["tabs"])
    return out
