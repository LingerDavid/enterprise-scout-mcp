"""Append collect results to EnterpriseLake warehouse/entities parquet."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from enterprise_scout_mcp.models import CollectResult, ResultGrade


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

    row = {
        "keyword": result.task.keyword,
        "platform": result.task.platform.value,
        "channel": result.channel.value,
        "grade": result.grade.value,
        "persona_id": result.persona_id,
        "message": result.message,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "payload_json": json.dumps(result.data, ensure_ascii=False),
    }
    table = pa.Table.from_pylist([row])

    if part_path.is_file():
        existing = pq.read_table(part_path)
        table = pa.concat_tables([existing, table])
    pq.write_table(table, part_path)
    return part_path
