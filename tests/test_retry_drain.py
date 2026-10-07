"""Retry-queue drain."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from enterprise_scout_mcp.models import ChannelKind, CollectResult, CollectTask, Platform, ResultGrade
from enterprise_scout_mcp.retry.drain import drain_retry_queue


def _write_job(path: Path, **kwargs) -> None:
    payload = {
        "keyword": "Acme",
        "platform": "aiqicha",
        "grade": "captcha",
        "fields": ["enterprise_info", "partner"],
        "depth": 1,
        "persona_id": "desktop_chrome_cn",
        "data": {},
    }
    payload.update(kwargs)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_drain_dry_run_lists_jobs(tmp_path: Path) -> None:
    queue = tmp_path / "retry_queue"
    queue.mkdir()
    _write_job(queue / "aiqicha_Acme_1.json")
    scheduler = MagicMock()
    summary = drain_retry_queue(
        scheduler, raw_dir=tmp_path, dry_run=True
    )
    assert summary.scanned == 1
    assert summary.retried == 1
    assert scheduler.run.call_count == 0
    assert (queue / "aiqicha_Acme_1.json").is_file()


def test_drain_archives_on_success(tmp_path: Path) -> None:
    queue = tmp_path / "retry_queue"
    queue.mkdir()
    job = queue / "aiqicha_Acme_1.json"
    _write_job(job)
    scheduler = MagicMock()
    scheduler.run.return_value = CollectResult(
        task=CollectTask(keyword="Acme", platform=Platform.AIQICHA),
        channel=ChannelKind.ENSCAN_GO,
        grade=ResultGrade.OK,
        data={"enterprise_info": [{"name": "Acme Co", "pid": "1"}]},
    )
    scheduler.maybe_import_neo4j.return_value = None
    summary = drain_retry_queue(scheduler, raw_dir=tmp_path)
    assert summary.succeeded == 1
    assert summary.archived == 1
    assert not job.is_file()
    assert (queue / ".archive" / "aiqicha_Acme_1.json").is_file()
    call_kw = scheduler.run.call_args.kwargs
    assert call_kw.get("import_neo4j") is False


def test_drain_keeps_file_on_failure(tmp_path: Path) -> None:
    queue = tmp_path / "retry_queue"
    queue.mkdir()
    job = queue / "aiqicha_Acme_1.json"
    _write_job(job)
    scheduler = MagicMock()
    scheduler.run.return_value = CollectResult(
        task=CollectTask(keyword="Acme", platform=Platform.AIQICHA),
        channel=ChannelKind.ENSCAN_GO,
        grade=ResultGrade.CAPTCHA,
        message="still captcha",
    )
    summary = drain_retry_queue(scheduler, raw_dir=tmp_path)
    assert summary.failed == 1
    assert job.is_file()
    refreshed = json.loads(job.read_text(encoding="utf-8"))
    assert refreshed["message"] == "still captcha"


def test_drain_include_partial(tmp_path: Path) -> None:
    (tmp_path / "retry_queue").mkdir()
    _write_job(
        tmp_path / "aiqicha_Partial_1.json",
        keyword="PartialCo",
        grade="partial",
    )
    scheduler = MagicMock()
    summary = drain_retry_queue(
        scheduler, raw_dir=tmp_path, include_partial=True, dry_run=True
    )
    assert summary.scanned == 1
    assert summary.results[0]["keyword"] == "PartialCo"
