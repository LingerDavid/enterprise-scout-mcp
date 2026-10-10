"""Append L3 / judicial corpus hits to warehouse/supplements/."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.models import CollectResult, ResultGrade
from enterprise_scout_mcp.output.corpus_schema import SUPPLEMENT_COLUMNS, supplement_row


def _normalize_row(row: dict) -> dict:
    return {col: row.get(col) for col in SUPPLEMENT_COLUMNS}


def append_corpus_supplement(result: CollectResult, warehouse_dir: Path) -> Path | None:
    if result.grade not in (ResultGrade.OK, ResultGrade.PARTIAL):
        return None
    row = supplement_row(result)
    if row is None:
        return None
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None

    bucket = "l3" if (result.data or {}).get("academic") else "judicial"
    out_dir = warehouse_dir / "supplements" / bucket
    out_dir.mkdir(parents=True, exist_ok=True)
    part_path = out_dir / "part.parquet"

    normalized = _normalize_row(row)
    rows = [normalized]
    if part_path.is_file():
        existing = pq.read_table(part_path).to_pylist()
        rows = [_normalize_row(r) for r in existing] + rows
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, part_path)
    return part_path
