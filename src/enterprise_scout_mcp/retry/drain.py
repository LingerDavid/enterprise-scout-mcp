"""Re-run jobs from raw/retry_queue (and optionally raw/ partial)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from enterprise_scout_mcp.defaults import DEFAULT_REGISTRY_FIELDS, DONE_GRADES
from enterprise_scout_mcp.models import CollectTask, Platform
from enterprise_scout_mcp.scheduler import CollectorScheduler


@dataclass
class DrainSummary:
    scanned: int = 0
    retried: int = 0
    succeeded: int = 0
    failed: int = 0
    archived: int = 0
    skipped: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "retried": self.retried,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "archived": self.archived,
            "skipped": self.skipped,
            "results": self.results,
        }


def _load_job(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _job_paths(queue_dir: Path, *, include_partial_raw: Path | None, limit: int) -> list[Path]:
    paths: list[Path] = []
    if queue_dir.is_dir():
        paths.extend(sorted(queue_dir.glob("*.json")))
    if include_partial_raw is not None and include_partial_raw.is_dir():
        for p in sorted(include_partial_raw.glob("*.json")):
            job = _load_job(p)
            if job and job.get("grade") == "partial":
                paths.append(p)
    if limit > 0:
        paths = paths[:limit]
    return paths


def _archive(path: Path, archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / path.name
    if dest.exists():
        dest = archive_dir / f"{path.stem}_dup{path.suffix}"
    shutil.move(str(path), str(dest))
    return dest


def drain_retry_queue(
    scheduler: CollectorScheduler,
    *,
    raw_dir: Path | str,
    limit: int = 0,
    include_partial: bool = False,
    dry_run: bool = False,
) -> DrainSummary:
    """Replay graded JSON jobs from retry_queue.

    On ok/partial: archive the source file under ``retry_queue/.archive/``.
    On captcha/error/blocked: leave the file in place (or refresh mtime via rewrite).
    """
    raw = Path(raw_dir)
    queue_dir = raw / "retry_queue"
    archive_dir = queue_dir / ".archive"
    partial_root = raw if include_partial else None

    summary = DrainSummary()
    for path in _job_paths(queue_dir, include_partial_raw=partial_root, limit=limit):
        summary.scanned += 1
        job = _load_job(path)
        if not job or not job.get("keyword"):
            summary.skipped += 1
            continue

        keyword = str(job["keyword"])
        platform_raw = str(job.get("platform") or "aiqicha")
        try:
            platform = Platform(platform_raw)
        except ValueError:
            summary.skipped += 1
            summary.results.append(
                {"file": path.name, "keyword": keyword, "status": "skip", "reason": "bad_platform"}
            )
            continue

        fields_raw = job.get("fields")
        if isinstance(fields_raw, list) and fields_raw:
            fields = tuple(str(f) for f in fields_raw)
        else:
            fields = DEFAULT_REGISTRY_FIELDS
        depth = int(job.get("depth") or 1)
        persona_id = str(job.get("persona_id") or "") or None

        if dry_run:
            summary.retried += 1
            summary.results.append(
                {
                    "file": path.name,
                    "keyword": keyword,
                    "platform": platform.value,
                    "status": "dry_run",
                }
            )
            continue

        task = CollectTask(keyword=keyword, platform=platform, fields=fields, depth=depth)
        result = scheduler.run(task, persona_id=persona_id, import_neo4j=False)
        summary.retried += 1
        grade = result.grade.value
        item = {
            "file": path.name,
            "keyword": keyword,
            "grade": grade,
            "channel": result.channel.value,
            "message": result.message,
        }
        summary.results.append(item)

        if grade in DONE_GRADES:
            summary.succeeded += 1
            _archive(path, archive_dir)
            summary.archived += 1
        else:
            summary.failed += 1
            # Refresh job metadata so next drain sees latest failure reason.
            job["grade"] = grade
            job["message"] = result.message
            job["channel"] = result.channel.value
            job["fields"] = list(fields)
            job["depth"] = depth
            path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

    if summary.succeeded > 0:
        neo_stats = scheduler.maybe_import_neo4j()
        if isinstance(neo_stats, dict):
            summary.results.append({"neo4j_import": neo_stats})
    return summary
