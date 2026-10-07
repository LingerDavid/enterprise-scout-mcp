"""Batch collection runner with summary counts."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    from pathlib import Path

    return parse_keywords(Path(path).read_text(encoding="utf-8"))


@dataclass
class BatchSummary:
    total: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"total": self.total, "counts": self.counts, "results": self.results}


def run_batch(
    scheduler: CollectorScheduler,
    keywords: Iterable[str],
    *,
    platform: Platform,
    depth: int = 1,
    fields: tuple[str, ...] = ("enterprise_info",),
    persona_id: str | None = None,
    stop_on_blocked: bool = False,
) -> BatchSummary:
    summary = BatchSummary()
    for keyword in keywords:
        task = CollectTask(keyword=keyword, platform=platform, fields=fields, depth=depth)
        result = scheduler.run(task, persona_id=persona_id)
        summary.total += 1
        grade = result.grade.value
        summary.counts[grade] = summary.counts.get(grade, 0) + 1
        summary.results.append(_result_item(result))
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
