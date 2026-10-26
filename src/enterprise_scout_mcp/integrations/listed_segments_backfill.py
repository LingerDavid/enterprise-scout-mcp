"""Batch backfill listed/segments from East Money F10 主营构成."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.output.listed_schema import to_tradecraft_symbol
from enterprise_scout_mcp.output.listed_writer import listed_part_path
from enterprise_scout_mcp.sources.eastmoney_segments import fetch_business_segments


def _read_identity_rows(warehouse_dir: Path) -> list[dict[str, Any]]:
    part = listed_part_path(warehouse_dir, "identity")
    if not part.is_file():
        return []
    try:
        import pyarrow.parquet as pq

        return pq.read_table(part).to_pylist()
    except Exception:
        return []


def _fetch_one(row: dict[str, Any]) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    sym = to_tradecraft_symbol(str(row.get("security_id") or ""))
    if not sym:
        return "", [], {"skipped": ["no_symbol"]}
    issuer_id = str(row.get("issuer_id") or "").strip()
    report = fetch_business_segments(sym, issuer_id=issuer_id)
    segs = report.get("segments") or []
    return sym, list(segs) if isinstance(segs, list) else [], report


def backfill_listed_segments(
    warehouse_dir: Path,
    *,
    workers: int = 12,
    limit: int | None = None,
    delay_s: float = 0.05,
    progress_path: Path | None = None,
) -> dict[str, Any]:
    """Fetch F10 segments for each identity row; write listed/segments parquet."""
    warehouse_dir = Path(warehouse_dir)
    identity = _read_identity_rows(warehouse_dir)
    if limit is not None:
        identity = identity[: max(0, int(limit))]

    summary: dict[str, Any] = {
        "warehouse_dir": str(warehouse_dir),
        "identity_rows": len(identity),
        "workers": workers,
        "segments_written": 0,
        "symbols_ok": 0,
        "symbols_skipped": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    if not identity:
        summary["error"] = "no_identity_rows"
        return summary

    segment_rows: list[dict[str, Any]] = []
    skipped_samples: list[dict[str, Any]] = []

    if workers <= 1 or len(identity) <= 1:
        for row in identity:
            sym, segs, rep = _fetch_one(row)
            if segs:
                summary["symbols_ok"] += 1
                segment_rows.extend(segs)
            else:
                summary["symbols_skipped"] += 1
                if len(skipped_samples) < 20:
                    skipped_samples.append({"symbol": sym, "skipped": rep.get("skipped")})
            if delay_s > 0:
                time.sleep(delay_s)
    else:
        cap = max(1, min(int(workers), len(identity)))
        with ThreadPoolExecutor(max_workers=cap) as ex:
            futures = {ex.submit(_fetch_one, row): row for row in identity}
            for fut in as_completed(futures):
                sym, segs, rep = fut.result()
                if segs:
                    summary["symbols_ok"] += 1
                    segment_rows.extend(segs)
                else:
                    summary["symbols_skipped"] += 1
                    if len(skipped_samples) < 20:
                        skipped_samples.append({"symbol": sym, "skipped": rep.get("skipped")})

    summary["segments_written"] = len(segment_rows)
    summary["skipped_samples"] = skipped_samples
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()

    if segment_rows:
        # Fresh write (segments table was missing).
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            summary["error"] = "pyarrow_missing"
            return summary
        part = listed_part_path(warehouse_dir, "segments")
        part.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(segment_rows), part)
        summary["segments_path"] = str(part)

    if progress_path is not None:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with progress_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return summary
