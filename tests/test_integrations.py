"""Integration helpers - cookies, aiqicha db, parquet."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from enterprise_scout_mcp.integrations.aiqicha_db import lookup_company
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
