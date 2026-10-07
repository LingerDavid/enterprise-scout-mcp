"""Append collect results to EnterpriseLake warehouse/entities parquet."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.models import CollectResult, ResultGrade
from enterprise_scout_mcp.output.entity_schema import entity_row


def append_entity(result: CollectResult, warehouse_dir: Path) -> Path | None:
    ok_grades = (ResultGrade.OK, ResultGrade.PARTIAL)
    if result.grade not in ok_grades:
        return None
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None

    entities_dir = warehouse_dir / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)
    part_path = entities_dir / "part.parquet"

    row = entity_row(result)
    row["message"] = result.message
    table = pa.Table.from_pylist([row])

    if part_path.is_file():
        existing = pq.read_table(part_path)
        table = pa.concat_tables([existing, table])
    pq.write_table(table, part_path)
    return part_path
