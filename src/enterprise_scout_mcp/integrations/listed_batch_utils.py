"""Shared helpers for parallel listed-warehouse backfills."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from enterprise_scout_mcp.output.listed_writer import listed_part_path


def read_identity_rows(warehouse_dir: Path) -> list[dict[str, Any]]:
    part = listed_part_path(warehouse_dir, "identity")
    if not part.is_file():
        return []
    try:
        import pyarrow.parquet as pq

        return pq.read_table(part).to_pylist()
    except Exception:
        return []


def read_listed_table(warehouse_dir: Path, table: str) -> list[dict[str, Any]]:
    part = listed_part_path(warehouse_dir, table)
    if not part.is_file():
        return []
    try:
        import pyarrow.parquet as pq

        return pq.read_table(part).to_pylist()
    except Exception:
        return []


def write_listed_table(warehouse_dir: Path, table: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None
    part = listed_part_path(warehouse_dir, table)
    part.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), part)
    return str(part)


def merge_listed_table(
    warehouse_dir: Path,
    table: str,
    rows: list[dict[str, Any]],
    *,
    drop_key: str,
    drop_values: set[str],
) -> str | None:
    """Replace rows whose ``drop_key`` is in ``drop_values``; keep other existing rows."""
    if not rows and not drop_values:
        return None
    existing = read_listed_table(warehouse_dir, table)
    kept = [r for r in existing if str(r.get(drop_key) or "") not in drop_values]
    merged = kept + rows
    if not merged:
        return None
    return write_listed_table(warehouse_dir, table, merged)


def run_identity_batch(
    identity: list[dict[str, Any]],
    fetch_one: Callable[[dict[str, Any]], tuple[str, list[dict[str, Any]], dict[str, Any]]],
    *,
    workers: int = 12,
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    """Parallel fetch over identity rows. Returns (rows, counts, skipped_samples)."""
    rows_out: list[dict[str, Any]] = []
    counts = {"ok": 0, "skipped": 0}
    skipped_samples: list[dict[str, Any]] = []

    if workers <= 1 or len(identity) <= 1:
        for row in identity:
            sym, rows, rep = fetch_one(row)
            if rows:
                counts["ok"] += 1
                rows_out.extend(rows)
            else:
                counts["skipped"] += 1
                if len(skipped_samples) < 20:
                    skipped_samples.append({"symbol": sym, "skipped": rep.get("skipped")})
        return rows_out, counts, skipped_samples

    cap = max(1, min(int(workers), len(identity)))
    with ThreadPoolExecutor(max_workers=cap) as ex:
        futures = {ex.submit(fetch_one, row): row for row in identity}
        for fut in as_completed(futures):
            sym, rows, rep = fut.result()
            if rows:
                counts["ok"] += 1
                rows_out.extend(rows)
            else:
                counts["skipped"] += 1
                if len(skipped_samples) < 20:
                    skipped_samples.append({"symbol": sym, "skipped": rep.get("skipped")})
    return rows_out, counts, skipped_samples
