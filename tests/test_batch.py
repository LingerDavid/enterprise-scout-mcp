"""Batch keyword parsing and summary."""

from __future__ import annotations

from unittest.mock import MagicMock

from enterprise_scout_mcp.batch import parse_keywords, run_batch
from enterprise_scout_mcp.models import ChannelKind, CollectResult, CollectTask, Platform, ResultGrade


def test_parse_keywords_dedupes() -> None:
    kws = parse_keywords("小米, 华为\n小米\n")
    assert kws == ["小米", "华为"]


def test_run_batch_summary() -> None:
    scheduler = MagicMock()
    scheduler.run.side_effect = [
        CollectResult(
            task=CollectTask(keyword="A", platform=Platform.AIQICHA),
            channel=ChannelKind.ENSCAN_GO,
            grade=ResultGrade.OK,
            data={"aiqicha_id": "1"},
        ),
        CollectResult(
            task=CollectTask(keyword="B", platform=Platform.AIQICHA),
            channel=ChannelKind.ENSCAN_GO,
            grade=ResultGrade.ERROR,
            message="fail",
        ),
    ]
    summary = run_batch(scheduler, ["A", "B"], platform=Platform.AIQICHA)
    assert summary.total == 2
    assert summary.counts["ok"] == 1
    assert summary.counts["error"] == 1
    assert len(summary.results) == 2
