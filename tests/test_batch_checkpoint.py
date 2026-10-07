"""Batch checkpoint resume."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from enterprise_scout_mcp.batch import run_batch
from enterprise_scout_mcp.models import ChannelKind, CollectResult, CollectTask, Platform, ResultGrade


def test_checkpoint_skips_done_keywords(tmp_path: Path) -> None:
    ckpt = tmp_path / "batch.json"
    scheduler = MagicMock()
    scheduler.run.side_effect = [
        CollectResult(
            task=CollectTask(keyword="B", platform=Platform.AIQICHA),
            channel=ChannelKind.ENSCAN_GO,
            grade=ResultGrade.OK,
            data={},
        ),
    ]
    # Pre-seed checkpoint with A done
    ckpt.write_text(
        '{"done": ["A"], "counts": {"ok": 1}, "results": [{"keyword": "A", "grade": "ok"}]}',
        encoding="utf-8",
    )
    summary = run_batch(
        scheduler,
        ["A", "B"],
        platform=Platform.AIQICHA,
        checkpoint_path=ckpt,
    )
    assert summary.skipped == 1
    assert summary.total == 1
    assert scheduler.run.call_count == 1
    assert "B" in str(ckpt.read_text(encoding="utf-8"))


def test_checkpoint_retries_error_and_captcha(tmp_path: Path) -> None:
    ckpt = tmp_path / "batch.json"
    scheduler = MagicMock()
    scheduler.run.side_effect = [
        CollectResult(
            task=CollectTask(keyword="A", platform=Platform.AIQICHA),
            channel=ChannelKind.ENSCAN_GO,
            grade=ResultGrade.ERROR,
            data={},
            message="down",
        ),
        CollectResult(
            task=CollectTask(keyword="B", platform=Platform.AIQICHA),
            channel=ChannelKind.ENSCAN_GO,
            grade=ResultGrade.CAPTCHA,
            data={},
        ),
        CollectResult(
            task=CollectTask(keyword="A", platform=Platform.AIQICHA),
            channel=ChannelKind.ENSCAN_GO,
            grade=ResultGrade.OK,
            data={"enterprise_info": [{"name": "A Co", "pid": "1"}]},
        ),
        CollectResult(
            task=CollectTask(keyword="B", platform=Platform.AIQICHA),
            channel=ChannelKind.ENSCAN_GO,
            grade=ResultGrade.OK,
            data={},
        ),
    ]
    run_batch(scheduler, ["A", "B"], platform=Platform.AIQICHA, checkpoint_path=ckpt)
    payload = json.loads(ckpt.read_text(encoding="utf-8"))
    assert payload["done"] == []  # neither ok/partial yet
    # Resume — should retry both
    summary = run_batch(scheduler, ["A", "B"], platform=Platform.AIQICHA, checkpoint_path=ckpt)
    assert summary.skipped == 0
    assert summary.total == 2
    payload = json.loads(ckpt.read_text(encoding="utf-8"))
    assert set(payload["done"]) == {"A", "B"}
    assert "fields" in payload
