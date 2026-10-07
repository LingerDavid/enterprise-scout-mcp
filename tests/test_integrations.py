"""Integration helpers - cookies, aiqicha db, parquet."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from unittest.mock import patch

from enterprise_scout_mcp.integrations.aiqicha_db import lookup_company
from enterprise_scout_mcp.integrations.aiqicha_runner import fetch_one, fetch_with_fallback
from enterprise_scout_mcp.integrations.enscan_cookies import sync_aiqicha_to_enscan
from enterprise_scout_mcp.models import ChannelKind, CollectResult, CollectTask, Platform, ResultGrade
from enterprise_scout_mcp.output.parquet_writer import append_entity


def test_sync_aiqicha_cookie(tmp_path: Path) -> None:
    cookie = tmp_path / "cookie.txt"
    cookie.write_text("session=abc123", encoding="utf-8")
    enscan = tmp_path / "config.yaml"
    enscan.write_text("version: 0.7\ncookies:\n  aiqicha: ''\n", encoding="utf-8")
    preview = sync_aiqicha_to_enscan(cookie_source=cookie, enscan_config=enscan)
    assert preview.startswith("session=abc123")
    assert "session=abc123" in enscan.read_text(encoding="utf-8")


def test_lookup_company(tmp_path: Path) -> None:
    db = tmp_path / "companies.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE companies (aiqicha_id TEXT PRIMARY KEY, company_name TEXT, former_name TEXT)"
    )
    conn.execute(
        "INSERT INTO companies VALUES ('123', 'Xiaomi', '小米科技')"
    )
    conn.commit()
    conn.close()
    hit = lookup_company("小米科技", db)
    assert hit is not None
    assert hit["aiqicha_id"] == "123"


def test_fetch_one_parses_json(tmp_path: Path) -> None:
    script = tmp_path / "fetch.py"
    script.write_text("print({\"status\": \"ok\", \"company\": {\"aiqicha_id\": \"9\"}})\n", encoding="utf-8")
    with patch("enterprise_scout_mcp.integrations.aiqicha_runner.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = '{"status": "ok", "company": {"aiqicha_id": "9"}}'
        run.return_value.stderr = ""
        payload = fetch_one("test", db_path=tmp_path / "x.db", cookie_file=None, script_path=script)
    assert payload["status"] == "ok"
    assert payload["company"]["aiqicha_id"] == "9"


def test_fetch_with_fallback_retries_nodriver_on_captcha(tmp_path: Path) -> None:
    httpx_script = tmp_path / "httpx.py"
    nodriver_script = tmp_path / "nodriver.py"
    httpx_script.write_text("", encoding="utf-8")
    nodriver_script.write_text("", encoding="utf-8")

    with patch("enterprise_scout_mcp.integrations.aiqicha_runner.fetch_one") as httpx_fetch:
        with patch("enterprise_scout_mcp.integrations.aiqicha_runner.run_script") as nodriver_run:
            httpx_fetch.return_value = {"status": "captcha"}
            nodriver_run.return_value = {"status": "ok", "company": {"aiqicha_id": "42"}}
            payload = fetch_with_fallback(
                "test",
                db_path=tmp_path / "x.db",
                cookie_file=None,
                httpx_script=httpx_script,
                nodriver_script=nodriver_script,
                nodriver_enabled=True,
                nodriver_user_data_dir=tmp_path / "nd",
                timeout_seconds=30.0,
            )
    assert payload["status"] == "ok"
    assert payload["company"]["aiqicha_id"] == "42"
    nodriver_run.assert_called_once()


@pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None,
    reason="pyarrow not installed",
)
def test_append_entity_parquet(tmp_path: Path) -> None:
    task = CollectTask(keyword="testco", platform=Platform.AIQICHA)
    result = CollectResult(
        task=task,
        channel=ChannelKind.PLAYWRIGHT,
        grade=ResultGrade.OK,
        data={"aiqicha_id": "1"},
        persona_id="p1",
    )
    path = append_entity(result, tmp_path)
    assert path is not None
    assert path.is_file()
