"""Append equity edges to EnterpriseLake warehouse/edges/equity/part.parquet."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from enterprise_scout_mcp.models import CollectResult, ResultGrade
from enterprise_scout_mcp.output.edge_extractor import extract_edges
from enterprise_scout_mcp.output.edge_schema import EDGE_COLUMNS


def _ensure_columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        row = {c: r.get(c, "") if c != "payload_json" else r.get(c, "{}") for c in EDGE_COLUMNS}
        if "credit_code" not in r:
            row["credit_code"] = ""
        out.append(row)
    return out


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep newest collected_at per (src_name, dst_name, relation)."""
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in rows:
        key = (
            str(r.get("src_name") or "").strip(),
            str(r.get("dst_name") or "").strip(),
            str(r.get("relation") or "").strip(),
        )
        if not key[0] or not key[1] or not key[2]:
            continue
        prev = best.get(key)
        if prev is None or str(r.get("collected_at") or "") >= str(prev.get("collected_at") or ""):
            best[key] = r
    return list(best.values())


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

    new_rows = _ensure_columns(rows)
    if part_path.is_file():
        existing = pq.read_table(part_path).to_pylist()
        existing = _ensure_columns(existing)
        merged = _dedupe_rows(existing + new_rows)
    else:
        merged = _dedupe_rows(new_rows)

    table = pa.Table.from_pylist(merged)
    pq.write_table(table, part_path)
    return part_path
