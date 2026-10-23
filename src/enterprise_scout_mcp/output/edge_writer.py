"""Append equity edges to EnterpriseLake warehouse/edges/equity/part.parquet."""

from __future__ import annotations

import os
import time
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


def _quarantine_corrupt(part_path: Path) -> None:
    stamp = time.strftime("%Y%m%d%H%M%S")
    dest = part_path.with_name(f"part.parquet.corrupt.{stamp}")
    try:
        part_path.replace(dest)
    except OSError:
        try:
            part_path.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            if part_path.is_file():
                part_path.unlink()
        except OSError:
            pass


def _read_edge_rows(part_path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    if not part_path.is_file():
        return []
    try:
        return _ensure_columns(pq.read_table(part_path).to_pylist())
    except Exception:
        _quarantine_corrupt(part_path)
        return []


def _write_merged(part_path: Path, rows: Sequence[dict[str, Any]]) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    part_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = part_path.with_suffix(".parquet.tmp")
    pq.write_table(pa.Table.from_pylist(list(rows)), tmp)
    os.replace(tmp, part_path)
    return part_path


class _EdgeFileLock:
    """Best-effort exclusive lock for edges/equity read-modify-write."""

    def __init__(self, part_path: Path, *, timeout_seconds: float = 60.0) -> None:
        self._lock_path = part_path.with_suffix(".parquet.lock")
        self._timeout = timeout_seconds
        self._fd: int | None = None

    def __enter__(self) -> "_EdgeFileLock":
        deadline = time.monotonic() + self._timeout
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self._fd = os.open(
                    str(self._lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(self._fd, str(os.getpid()).encode("ascii", errors="ignore"))
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    # Stale lock: take over after timeout.
                    try:
                        self._lock_path.unlink()
                    except OSError:
                        pass
                    continue
                time.sleep(0.05)

    def __exit__(self, *exc: object) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            self._lock_path.unlink()
        except OSError:
            pass


def merge_edge_rows(warehouse_dir: Path, rows: Iterable[dict[str, Any]]) -> Path | None:
    """Merge pre-built edge rows into ``edges/equity/part.parquet`` (dedupe by triple)."""
    new_rows = _ensure_columns(list(rows))
    if not new_rows:
        return None
    try:
        import pyarrow.parquet  # noqa: F401
    except ImportError:
        return None

    part_path = equity_edges_part_path(warehouse_dir)
    with _EdgeFileLock(part_path):
        existing = _read_edge_rows(part_path)
        merged = _dedupe_rows(existing + new_rows)
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
        import pyarrow.parquet  # noqa: F401
    except ImportError:
        return None

    new_rows = _ensure_columns(list(rows))
    part_path = equity_edges_part_path(warehouse_dir)
    with _EdgeFileLock(part_path):
        kept: list[dict[str, Any]] = []
        for r in _read_edge_rows(part_path):
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
