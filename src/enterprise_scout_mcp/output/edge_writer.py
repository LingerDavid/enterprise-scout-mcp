"""Append equity edges to EnterpriseLake warehouse/edges/equity/part.parquet."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.models import CollectResult, ResultGrade
from enterprise_scout_mcp.output.edge_extractor import extract_edges


def append_edges(result: CollectResult, warehouse_dir: Path) -> Path | None:
    ok_grades = (ResultGrade.OK, ResultGrade.PARTIAL)
    if result.grade not in ok_grades:
        return None

    rows = extract_edges(result)
    if not rows:
        return None

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None

    out_dir = warehouse_dir / "edges" / "equity"
    out_dir.mkdir(parents=True, exist_ok=True)
    part_path = out_dir / "part.parquet"
    table = pa.Table.from_pylist(rows)

    if part_path.is_file():
        existing = pq.read_table(part_path)
        table = pa.concat_tables([existing, table])
    pq.write_table(table, part_path)
    return part_path
