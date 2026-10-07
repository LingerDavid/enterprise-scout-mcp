"""Batch collection runner with summary counts and optional checkpoint."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from enterprise_scout_mcp.models import CollectResult, CollectTask, Platform
from enterprise_scout_mcp.scheduler import CollectorScheduler


def parse_keywords(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for line in text.replace(",", "\n").splitlines():
        kw = line.strip()
        if kw and kw not in seen:
            seen.add(kw)
            out.append(kw)
    return out


def keywords_from_file(path: str) -> list[str]:
    return parse_keywords(Path(path).read_text(encoding="utf-8"))


@dataclass
class BatchSummary:
    total: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    results: list[dict] = field(default_factory=list)
    skipped: int = 0
    checkpoint_path: str = ""

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "skipped": self.skipped,
            "counts": self.counts,
            "results": self.results,
            "checkpoint_path": self.checkpoint_path,
        }


def _load_checkpoint(path: Path) -> dict:
    if not path.is_file():
        return {"done": [], "counts": {}, "results": []}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError:
        return {"done": [], "counts": {}, "results": []}


def _save_checkpoint(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_batch(
    scheduler: CollectorScheduler,
    keywords: Iterable[str],
    *,
    platform: Platform,
    depth: int = 1,
    fields: tuple[str, ...] = ("enterprise_info",),
    persona_id: str | None = None,
    stop_on_blocked: bool = False,
    checkpoint_path: Path | str | None = None,
) -> BatchSummary:
    summary = BatchSummary()
    kws = list(keywords)
    done: set[str] = set()
    ckpt: dict | None = None
    ckpt_file: Path | None = None

    if checkpoint_path is not None:
        ckpt_file = Path(checkpoint_path)
        ckpt = _load_checkpoint(ckpt_file)
        done = set(ckpt.get("done") or [])
        summary.counts = dict(ckpt.get("counts") or {})
        summary.results = list(ckpt.get("results") or [])
        summary.checkpoint_path = str(ckpt_file)

    for keyword in kws:
        if keyword in done:
            summary.skipped += 1
            continue
        task = CollectTask(keyword=keyword, platform=platform, fields=fields, depth=depth)
        result = scheduler.run(task, persona_id=persona_id)
        summary.total += 1
        grade = result.grade.value
        summary.counts[grade] = summary.counts.get(grade, 0) + 1
        item = _result_item(result)
        summary.results.append(item)
        done.add(keyword)
        if ckpt_file is not None:
            _save_checkpoint(
                ckpt_file,
                {
                    "done": sorted(done),
                    "counts": summary.counts,
                    "results": summary.results,
                    "platform": platform.value,
                    "depth": depth,
                },
            )
        if stop_on_blocked and grade in ("blocked", "captcha"):
            break
    return summary


def _result_item(result: CollectResult) -> dict:
    data = result.data or {}
    return {
        "keyword": result.task.keyword,
        "grade": result.grade.value,
        "channel": result.channel.value,
        "message": result.message,
        "entity_id": str(data.get("aiqicha_id") or data.get("entity_id") or data.get("nameId") or ""),
    }
