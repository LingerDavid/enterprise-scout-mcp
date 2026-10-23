"""Append equity edges to EnterpriseLake warehouse/edges/equity/part.parquet."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

from enterprise_scout_mcp.models import CollectResult, ResultGrade
from enterprise_scout_mcp.output.edge_extractor import extract_edges
from enterprise_scout_mcp.output.edge_schema import EDGE_COLUMNS


def equity_edges_part_path(warehouse_dir: Path) -> Path:
    return Path(warehouse_dir) / "edges" / "equity" / "part.parquet"


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


def _write_merged(part_path: Path, rows: Sequence[dict[str, Any]]) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    part_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(list(rows)), part_path)
    return part_path


def merge_edge_rows(warehouse_dir: Path, rows: Iterable[dict[str, Any]]) -> Path | None:
    """Merge pre-built edge rows into ``edges/equity/part.parquet`` (dedupe by triple)."""
    new_rows = _ensure_columns(list(rows))
    if not new_rows:
        return None
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return None

    part_path = equity_edges_part_path(warehouse_dir)
    if part_path.is_file():
        existing = _ensure_columns(pq.read_table(part_path).to_pylist())
        merged = _dedupe_rows(existing + new_rows)
    else:
        merged = _dedupe_rows(new_rows)
    return _write_merged(part_path, merged)


def replace_edges_for_source(
    warehouse_dir: Path,
    rows: Iterable[dict[str, Any]],
    *,
    query_keyword: str,
    source_channel: str,
) -> Path | None:
    """Drop prior edges for (query_keyword, source_channel), then merge ``rows``.

    Empty ``rows`` still drops matching prior rows (refresh wipe). Returns None
    when pyarrow is missing or nothing remains and nothing was written.
    """
    keyword = str(query_keyword or "").strip()
    channel = str(source_channel or "").strip()
    if not keyword or not channel:
        return None
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return None

    new_rows = _ensure_columns(list(rows))
    part_path = equity_edges_part_path(warehouse_dir)
    kept: list[dict[str, Any]] = []
    if part_path.is_file():
        for r in _ensure_columns(pq.read_table(part_path).to_pylist()):
            if (
                str(r.get("query_keyword") or "").strip() == keyword
                and str(r.get("source_channel") or "").strip() == channel
            ):
                continue
            kept.append(r)
    merged = _dedupe_rows(kept + new_rows)
    if not merged and not part_path.is_file():
        return None
    return _write_merged(part_path, merged)


def append_edges(result: CollectResult, warehouse_dir: Path) -> Path | None:
    ok_grades = (ResultGrade.OK, ResultGrade.PARTIAL)
    if result.grade not in ok_grades:
        return None

    rows = extract_edges(result)
    if not rows:
        return None
    return merge_edge_rows(warehouse_dir, rows)
