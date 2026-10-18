"""Append listed-company rows to EnterpriseLake warehouse/listed/*/part.parquet."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from enterprise_scout_mcp.output.listed_schema import (
    CAPITAL_COLUMNS,
    FACTS_COLUMNS,
    HOLDERS_COLUMNS,
    IDENTITY_COLUMNS,
    LISTED_CONTROL_COLUMNS,
    SEGMENTS_COLUMNS,
    SUBSIDIARIES_COLUMNS,
)

_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "identity": IDENTITY_COLUMNS,
    "facts": FACTS_COLUMNS,
    "segments": SEGMENTS_COLUMNS,
    "capital": CAPITAL_COLUMNS,
    "holders": HOLDERS_COLUMNS,
    "subsidiaries": SUBSIDIARIES_COLUMNS,
}


def listed_part_path(warehouse_dir: Path, table: str) -> Path:
    if table == "listed_control":
        return warehouse_dir / "edges" / "listed_control" / "part.parquet"
    if table not in _TABLE_COLUMNS:
        raise ValueError(f"unknown listed table: {table}")
    return warehouse_dir / "listed" / table / "part.parquet"


def _normalize_rows(table: str, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    if table == "listed_control":
        columns = LISTED_CONTROL_COLUMNS
    else:
        columns = _TABLE_COLUMNS[table]
    out: list[dict[str, Any]] = []
    for raw in rows:
        out.append({key: raw.get(key, "") for key in columns})
    return out


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
