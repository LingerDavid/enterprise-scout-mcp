"""Iteratively collect missing equity neighbors via aiqicha (never tianyancha)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from enterprise_scout_mcp.defaults import DEFAULT_REGISTRY_FIELDS
from enterprise_scout_mcp.models import CollectResult, CollectTask, Platform, ResultGrade
from enterprise_scout_mcp.warehouse.equity_tree import (
    build_equity_tree,
    looks_like_corporation,
    normalize_name,
)

_TYC_BLOCKED = frozenset({"tianyancha", "tyc"})


def assert_aqc_platform(platform: str | Platform) -> Platform:
    raw = platform.value if isinstance(platform, Platform) else str(platform).strip().lower()
    if raw in _TYC_BLOCKED or raw == Platform.TIANYANCHA.value:
        raise ValueError("equity_expand refuses tianyancha/tyc; use aiqicha (aqc)")
    if raw in ("aiqicha", "aqc", Platform.AIQICHA.value):
        return Platform.AIQICHA
    # expand always forces aiqicha regardless of other platforms
    if raw and raw not in ("aiqicha", Platform.AIQICHA.value):
        raise ValueError(f"equity_expand forces aiqicha; got {raw!r}")
    return Platform.AIQICHA


CollectFn = Callable[[CollectTask], CollectResult]


def expand_equity_tree(
    warehouse_dir: Path,
    center: str,
    *,
    collect_fn: CollectFn,
    max_depth: int = 2,
    min_ratio: float = 20.0,
    max_nodes: int = 200,
    max_collects: int = 30,
    fields: tuple[str, ...] = DEFAULT_REGISTRY_FIELDS,
) -> dict[str, Any]:
    """BFS-fill missing corporate neighbors with depth=1 aqc collects."""
    assert_aqc_platform(Platform.AIQICHA)
    collected: list[str] = []
    skipped_persons: list[str] = []
    errors: list[dict[str, str]] = []
    rounds = 0
    quota_stopped = False
    seen_attempt: set[str] = set()

    tree = build_equity_tree(
        warehouse_dir,
        center,
        max_depth=max_depth,
        min_ratio=min_ratio,
        max_nodes=max_nodes,
        include_supply=False,
    )

    while len(collected) < max_collects:
        missing = [
            m
            for m in (tree.get("missing_neighbors") or [])
            if looks_like_corporation(m) and normalize_name(m) not in seen_attempt
        ]
        # persons already filtered by looks_like; double-check
        persons = [
            m
            for m in (tree.get("missing_neighbors") or [])
            if not looks_like_corporation(m)
        ]
        for p in persons:
            if p not in skipped_persons:
                skipped_persons.append(p)

        if not missing:
            break

        rounds += 1
        batch = missing[: max(1, max_collects - len(collected))]
        progressed = False
        for name in batch:
            key = normalize_name(name)
            if key in seen_attempt:
                continue
            seen_attempt.add(key)
            if len(collected) >= max_collects:
                break
            task = CollectTask(
                keyword=name,
                platform=Platform.AIQICHA,
                fields=fields,
                depth=1,
                invest_min=min_ratio if min_ratio > 0 else None,
            )
            try:
                result = collect_fn(task)
            except Exception as exc:  # noqa: BLE001 — soft per-neighbor
                msg = str(exc)
                if "quota" in msg.lower():
                    quota_stopped = True
                    errors.append({"keyword": name, "error": msg})
                    break
                errors.append({"keyword": name, "error": msg})
                continue

            if result.grade in (ResultGrade.OK, ResultGrade.PARTIAL):
                collected.append(name)
                progressed = True
            else:
                err = result.message or result.grade.value
                if "quota" in err.lower():
                    quota_stopped = True
                    errors.append({"keyword": name, "error": err})
                    break
                errors.append({"keyword": name, "error": err})

        tree = build_equity_tree(
            warehouse_dir,
            center,
            max_depth=max_depth,
            min_ratio=min_ratio,
            max_nodes=max_nodes,
            include_supply=False,
        )
        if quota_stopped or not progressed:
            break

    return {
        "ok": True,
        "collected": collected,
        "skipped_persons": skipped_persons,
        "rounds": rounds,
        "quota_stopped": quota_stopped,
        "errors": errors,
        "tree": tree,
        "platform": Platform.AIQICHA.value,
        "min_ratio": min_ratio,
        "max_depth": max_depth,
        "max_collects": max_collects,
    }
