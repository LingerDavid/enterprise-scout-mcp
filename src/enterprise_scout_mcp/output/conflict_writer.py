"""Append L1/L2 registry conflicts to warehouse/conflicts parquet."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def append_conflicts(rows: list[dict[str, Any]], warehouse_dir: Path) -> Path | None:
    if not rows:
        return None
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None

    out_dir = warehouse_dir / "conflicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    part_path = out_dir / "part.parquet"
    table = pa.Table.from_pylist(rows)
    if part_path.is_file():
        existing = pq.read_table(part_path)
        table = pa.concat_tables([existing, table])
    pq.write_table(table, part_path)
    return part_path
