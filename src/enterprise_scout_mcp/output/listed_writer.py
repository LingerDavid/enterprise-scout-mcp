"""Append / replace listed-company rows in EnterpriseLake warehouse parquet."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

from enterprise_scout_mcp.output.listed_schema import (
    CAPITAL_COLUMNS,
    DIVIDENDS_COLUMNS,
    EXECUTIVES_COLUMNS,
    FACTS_COLUMNS,
    HOLDERS_COLUMNS,
    IDENTITY_COLUMNS,
    LISTED_CONTROL_COLUMNS,
    SEGMENTS_COLUMNS,
    SUBSIDIARIES_COLUMNS,
    ALLOTMENT_ISSUE_COLUMNS,
    CAPITAL_HISTORY_COLUMNS,
    DIVIDEND_SUMMARY_COLUMNS,
    RESTRICTED_UNLOCK_COLUMNS,
    EXEC_HOLDING_CHANGES_COLUMNS,
    FLOAT_HOLDERS_COLUMNS,
    FLOAT_SHARE_MIX_COLUMNS,
    FUND_HOLDINGS_COLUMNS,
    SEO_ISSUE_COLUMNS,
    HOLDER_STATS_COLUMNS,
    INSTITUTIONAL_HOLDINGS_COLUMNS,
    IPO_PROFILE_COLUMNS,
    WORKFORCE_COLUMNS,
    WORKFORCE_EDUCATION_COLUMNS,
)

_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "identity": IDENTITY_COLUMNS,
    "facts": FACTS_COLUMNS,
    "segments": SEGMENTS_COLUMNS,
    "capital": CAPITAL_COLUMNS,
    "holders": HOLDERS_COLUMNS,
    "subsidiaries": SUBSIDIARIES_COLUMNS,
    "executives": EXECUTIVES_COLUMNS,
    "dividends": DIVIDENDS_COLUMNS,
    "workforce": WORKFORCE_COLUMNS,
    "workforce_education": WORKFORCE_EDUCATION_COLUMNS,
    "holder_stats": HOLDER_STATS_COLUMNS,
    "ipo_profile": IPO_PROFILE_COLUMNS,
    "float_holders": FLOAT_HOLDERS_COLUMNS,
    "institutional_holdings": INSTITUTIONAL_HOLDINGS_COLUMNS,
    "exec_holding_changes": EXEC_HOLDING_CHANGES_COLUMNS,
    "fund_holdings": FUND_HOLDINGS_COLUMNS,
    "float_share_mix": FLOAT_SHARE_MIX_COLUMNS,
    "dividend_summary": DIVIDEND_SUMMARY_COLUMNS,
    "seo_issues": SEO_ISSUE_COLUMNS,
    "capital_history": CAPITAL_HISTORY_COLUMNS,
    "allotment_issues": ALLOTMENT_ISSUE_COLUMNS,
    "restricted_unlock": RESTRICTED_UNLOCK_COLUMNS,
}


def listed_part_path(warehouse_dir: Path, table: str) -> Path:
    if table == "listed_control":
        return warehouse_dir / "edges" / "listed_control" / "part.parquet"
    if table not in _TABLE_COLUMNS:
        raise ValueError(f"unknown listed table: {table}")
    return warehouse_dir / "listed" / table / "part.parquet"


def _columns_for(table: str) -> tuple[str, ...]:
    if table == "listed_control":
        return LISTED_CONTROL_COLUMNS
    if table not in _TABLE_COLUMNS:
        raise ValueError(f"unknown listed table: {table}")
    return _TABLE_COLUMNS[table]


def _normalize_rows(table: str, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    columns = _columns_for(table)
    out: list[dict[str, Any]] = []
    for raw in rows:
        out.append({key: raw.get(key, "") for key in columns})
    return out


def _row_key(row: dict[str, Any], match_keys: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(row.get(k) or "") for k in match_keys)


def append_listed_rows(
    warehouse_dir: Path,
    table: str,
    rows: Iterable[dict[str, Any]],
) -> Path | None:
    """Append rows. Returns part path, or None when empty / pyarrow missing."""
    normalized = _normalize_rows(table, rows)
    if not normalized:
        return None
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None

    part_path = listed_part_path(warehouse_dir, table)
    part_path.parent.mkdir(parents=True, exist_ok=True)
    table_pa = pa.Table.from_pylist(normalized)
    if part_path.is_file():
        existing = pq.read_table(part_path)
        table_pa = pa.concat_tables([existing, table_pa])
    pq.write_table(table_pa, part_path)
    return part_path


def replace_listed_rows(
    warehouse_dir: Path,
    table: str,
    rows: Iterable[dict[str, Any]],
    *,
    match_keys: Sequence[str],
) -> Path | None:
    """Drop existing rows whose key matches any incoming row, then write the new set.

    Empty ``rows`` is a no-op (returns None). Keys with any empty component still match.
    """
    normalized = _normalize_rows(table, rows)
    if not normalized:
        return None
    if not match_keys:
        raise ValueError("match_keys required for replace")
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None

    drop_keys = {_row_key(row, match_keys) for row in normalized}
    kept: list[dict[str, Any]] = []
    part_path = listed_part_path(warehouse_dir, table)
    if part_path.is_file():
        for old in pq.read_table(part_path).to_pylist():
            if _row_key(old, match_keys) not in drop_keys:
                kept.append({key: old.get(key, "") for key in _columns_for(table)})

    merged = kept + normalized
    part_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(merged), part_path)
    return part_path
