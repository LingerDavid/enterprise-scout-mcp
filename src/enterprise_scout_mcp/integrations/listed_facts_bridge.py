"""Bridge tradecraft panel financials parquet → EnterpriseLake listed/facts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.integrations.listed_batch_utils import read_identity_rows, write_listed_table
from enterprise_scout_mcp.output.listed_schema import to_tradecraft_symbol

logger = logging.getLogger(__name__)

_PANEL_TABLES = ("income", "balance_sheet", "cash_flow")

_SUFFIX_EXCHANGE = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}

_CANONICAL_TO_ITEM: dict[str, tuple[str, str]] = {
    "revenue": ("income", "revenue"),
    "operating_cost": ("income", "operating_cost"),
    "operating_profit": ("income", "operating_profit"),
    "selling_expense": ("income", "selling_exp"),
    "admin_expense": ("income", "admin_exp"),
    "rd_expense": ("income", "rd_exp"),
    "financial_expense": ("income", "finance_exp"),
    "non_operating_income": ("income", "non_operating_income"),
    "non_operating_expense": ("income", "non_operating_expense"),
    "total_profit": ("income", "profit_before_tax"),
    "income_tax": ("income", "income_tax"),
    "net_income": ("income", "net_profit"),
    "net_income_attributable": ("income", "net_profit_parent"),
    "net_income_deducted": ("income", "net_profit_parent_ex_nonrecurring"),
    "cash_and_equivalents": ("balance", "cash"),
    "accounts_receivable": ("balance", "accounts_receivable"),
    "inventory": ("balance", "inventory"),
    "goodwill": ("balance", "goodwill"),
    "fixed_assets": ("balance", "fixed_assets"),
    "intangible_assets": ("balance", "intangible"),
    "total_assets": ("balance", "total_assets"),
    "short_term_borrowing": ("balance", "short_term_borrowings"),
    "long_term_borrowing": ("balance", "long_term_borrowings"),
    "accounts_payable": ("balance", "accounts_payable"),
    "total_liabilities": ("balance", "total_liabilities"),
    "equity_attributable": ("balance", "equity_parent"),
    "minority_interest": ("balance", "equity_minority"),
    "total_equity": ("balance", "total_equity"),
    "net_operating_cash_flow": ("cashflow", "cfo"),
    "cash_from_sales": ("cashflow", "cash_from_sales"),
    "capex": ("cashflow", "capex_cash"),
    "dividends_paid": ("cashflow", "dividends_paid"),
    "buyback_cash": ("cashflow", "buyback_cash"),
    "net_investing_cash_flow": ("cashflow", "cfi"),
    "net_financing_cash_flow": ("cashflow", "cff"),
}


def symbol_to_security_id(symbol: str) -> str | None:
    raw = str(symbol or "").strip().upper()
    if "." not in raw:
        return None
    code, suffix = raw.rsplit(".", 1)
    exchange = _SUFFIX_EXCHANGE.get(suffix)
    if not exchange or not code:
        return None
    return f"{exchange}:{code}"


def period_from_end(period_end: str) -> str | None:
    digits = "".join(ch for ch in str(period_end or "") if ch.isdigit())
    if len(digits) < 8:
        return None
    year, month, day = digits[:4], digits[4:6], digits[6:8]
    if month == "12" and day == "31":
        return year
    if month == "06" and day == "30":
        return f"{year}H1"
    if month == "03" and day == "31":
        return f"{year}Q1"
    if month == "09" and day == "30":
        return f"{year}Q3"
    return None


def _announce_day(value: Any) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) < 8:
        return ""
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def facts_from_panel_row(row: dict[str, Any], *, issuer_id: str) -> list[dict[str, str]]:
    period = period_from_end(str(row.get("period_end") or ""))
    if period is None:
        return []
    issuer = str(issuer_id or "").strip()
    if not issuer:
        return []
    document_date = _announce_day(row.get("announce_date"))
    doc = str(row.get("document_id") or "") or f"panel:{issuer}:{period}"
    out: list[dict[str, str]] = []
    for column, (statement, item_code) in _CANONICAL_TO_ITEM.items():
        raw = row.get(column)
        if raw is None or raw == "":
            continue
        out.append(
            {
                "issuer_id": issuer,
                "period": period,
                "scope": "consolidated",
                "statement": statement,
                "item_code": item_code,
                "label": column,
                "value": str(raw),
                "unit": "CNY",
                "currency": "CNY",
                "scale_in_source": "",
                "derived": "false",
                "document_id": doc,
                "document_date": document_date,
                "audit_opinion": "",
                "collected_at": "",
                "supersedes_ref": "",
            }
        )
    return out


def issuer_id_by_security(warehouse_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in read_identity_rows(warehouse_dir):
        sid = str(row.get("security_id") or "").strip()
        iid = str(row.get("issuer_id") or "").strip()
        if sid and iid:
            out[sid] = iid
    return out


def merge_panel_frames(frames: dict[str, Any]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for name in _PANEL_TABLES:
        frame = frames.get(name)
        if frame is None:
            continue
        if isinstance(frame, list):
            rows = [r for r in frame if isinstance(r, dict)]
        else:
            to_dicts = getattr(frame, "to_dicts", None)
            if not callable(to_dicts):
                continue
            rows = list(to_dicts())
        for row in rows:
            sym = str(row.get("symbol") or "").strip().upper()
            pe_raw = str(row.get("period_end") or "").strip()
            digits = "".join(ch for ch in pe_raw if ch.isdigit())
            if not sym or len(digits) < 8:
                continue
            pe = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
            key = (sym, pe)
            cur = by_key.setdefault(key, {"symbol": sym, "period_end": pe})
            for k, v in row.items():
                if k in {"symbol", "period_end"}:
                    continue
                if v is None or v == "":
                    continue
                cur[k] = v
    return list(by_key.values())


def load_panel_frames(panel_dir: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    root = Path(panel_dir) / "financials"
    for name in _PANEL_TABLES:
        path = root / name / "part.parquet"
        if not path.is_file():
            logger.warning("panel financials missing: %s", path)
            continue
        try:
            import pyarrow.parquet as pq

            out[name] = pq.read_table(path).to_pylist()
        except Exception as exc:
            logger.warning("read %s failed: %s", path, exc)
    return out


def _dedupe_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("issuer_id") or ""),
            str(row.get("period") or ""),
            str(row.get("scope") or ""),
            str(row.get("statement") or ""),
            str(row.get("item_code") or ""),
        )
        seen[key] = row
    return list(seen.values())


def sync_panel_to_listed_facts(
    panel_dir: Path,
    warehouse_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Read tradecraft ``data/financials/*`` and rewrite ``listed/facts``."""
    from datetime import datetime, timezone

    warehouse_dir = Path(warehouse_dir)
    panel_dir = Path(panel_dir)
    collected_at = datetime.now(timezone.utc).isoformat()
    frames = load_panel_frames(panel_dir)
    merged = merge_panel_frames(frames)
    issuer_map = issuer_id_by_security(warehouse_dir)

    facts: list[dict[str, Any]] = []
    linked = 0
    symbols: set[str] = set()
    for row in merged:
        security_id = symbol_to_security_id(str(row.get("symbol") or ""))
        issuer_id = ""
        if security_id:
            issuer_id = str(issuer_map.get(security_id) or security_id)
            if issuer_id != security_id:
                linked += 1
        for fact in facts_from_panel_row(row, issuer_id=issuer_id):
            fact["collected_at"] = collected_at
            facts.append(fact)
        if security_id:
            symbols.add(str(row.get("symbol") or ""))

    facts = _dedupe_facts(facts)
    report: dict[str, Any] = {
        "ok": True,
        "panel_dir": str(panel_dir),
        "panel_period_rows": len(merged),
        "symbols": len(symbols),
        "facts": len(facts),
        "issuer_linked": linked,
        "identity_map": len(issuer_map),
        "dry_run": dry_run,
        "path": None,
        "panel_tables": {k: (0 if v is None else len(v)) for k, v in frames.items()},
    }
    if dry_run:
        return report

    path = write_listed_table(warehouse_dir, "facts", facts)
    report["path"] = path
    if path is None:
        report["ok"] = False
        report["error"] = "pyarrow_write_failed_or_empty"
    return report
