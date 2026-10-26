"""In-warehouse peer comparison (East Money 同行比较 style, computed not scraped)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from enterprise_scout_mcp.integrations.listed_batch_utils import read_identity_rows
from enterprise_scout_mcp.output.listed_writer import listed_part_path
from enterprise_scout_mcp.sources.cninfo import resolve_listing


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        import pyarrow.parquet as pq

        return pq.read_table(path).to_pylist()
    except Exception:
        return []


def _percentile(value: float, population: list[float]) -> float | None:
    if not population:
        return None
    below = sum(1 for v in population if v < value)
    return round(100.0 * below / len(population), 1)


def _fact_value(facts: list[dict[str, Any]], issuer_id: str, period: str, item_code: str) -> float | None:
    for row in facts:
        if (
            str(row.get("issuer_id") or "") == issuer_id
            and str(row.get("period") or "") == period
            and str(row.get("item_code") or "") == item_code
        ):
            try:
                return float(row.get("value") or "")
            except (TypeError, ValueError):
                return None
    return None


def peer_compare(
    warehouse_dir: Path,
    symbol_or_security: str,
    *,
    period: str = "",
    min_peers: int = 8,
) -> dict[str, Any]:
    """Compare issuer to CSRC industry peers on revenue growth and net margin."""
    listing = resolve_listing(symbol_or_security)
    if listing is None:
        return {"ok": False, "skipped": ["unresolved_symbol"]}
    security_id, _code, _col = listing

    identity_rows = read_identity_rows(warehouse_dir)
    target = next((r for r in identity_rows if str(r.get("security_id") or "") == security_id), None)
    if target is None:
        return {"ok": False, "security_id": security_id, "skipped": ["no_identity"]}

    issuer_id = str(target.get("issuer_id") or security_id)
    industry = str(target.get("csrc_industry_l2") or target.get("csrc_industry_l1") or "").strip()
    if not industry:
        return {"ok": False, "security_id": security_id, "skipped": ["no_industry"]}

    facts = _read_parquet(listed_part_path(warehouse_dir, "facts"))
    if not facts:
        return {"ok": False, "security_id": security_id, "skipped": ["no_facts"]}

    annual_periods = sorted(
        {str(r.get("period") or "") for r in facts if str(r.get("period") or "").isdigit() and len(str(r.get("period"))) == 4}
    )
    if not annual_periods:
        return {"ok": False, "security_id": security_id, "skipped": ["no_annual_facts"]}
    use_period = period if period in annual_periods else annual_periods[-1]
    prev_period = str(int(use_period) - 1) if use_period.isdigit() else ""

    peers = [
        r
        for r in identity_rows
        if str(r.get("csrc_industry_l2") or r.get("csrc_industry_l1") or "").strip() == industry
    ]
    peer_issuer_ids = [str(r.get("issuer_id") or r.get("security_id") or "") for r in peers]

    revenues: list[float] = []
    margins: list[float] = []
    growths: list[float] = []
    for iid in peer_issuer_ids:
        rev = _fact_value(facts, iid, use_period, "revenue")
        np = _fact_value(facts, iid, use_period, "net_profit_parent")
        if rev is not None and rev > 0:
            revenues.append(rev)
        if rev is not None and rev > 0 and np is not None:
            margins.append(np / rev)
        if prev_period:
            prev_rev = _fact_value(facts, iid, prev_period, "revenue")
            if rev is not None and prev_rev is not None and prev_rev > 0:
                growths.append((rev - prev_rev) / prev_rev)

    target_rev = _fact_value(facts, issuer_id, use_period, "revenue")
    target_np = _fact_value(facts, issuer_id, use_period, "net_profit_parent")
    target_margin = (target_np / target_rev) if target_rev and target_rev > 0 and target_np is not None else None
    target_growth = None
    if prev_period and target_rev is not None:
        prev_rev = _fact_value(facts, issuer_id, prev_period, "revenue")
        if prev_rev is not None and prev_rev > 0:
            target_growth = (target_rev - prev_rev) / prev_rev

    n = len(peer_issuer_ids)
    out: dict[str, Any] = {
        "ok": True,
        "security_id": security_id,
        "issuer_id": issuer_id,
        "industry": industry,
        "period": use_period,
        "peer_count": n,
        "min_peers": min_peers,
        "sample_sufficient": n >= min_peers,
        "metrics": {},
    }
    if n < min_peers:
        out["skipped"] = ["insufficient_peers"]
        return out

    if target_rev is not None and revenues:
        out["metrics"]["revenue"] = {
            "value": target_rev,
            "percentile": _percentile(target_rev, revenues),
        }
    if target_margin is not None and margins:
        out["metrics"]["net_margin"] = {
            "value": round(target_margin, 4),
            "percentile": _percentile(target_margin, margins),
        }
    if target_growth is not None and growths:
        out["metrics"]["revenue_yoy"] = {
            "value": round(target_growth, 4),
            "percentile": _percentile(target_growth, growths),
        }
    out["note"] = "库内分位；同行业同 period 样本"
    return out
