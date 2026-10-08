"""Unified sessions config wiring."""

from __future__ import annotations

import json
from pathlib import Path

from enterprise_scout_mcp.config import AppConfig, SessionsConfig
from enterprise_scout_mcp.sessions.registry import import_session, list_sessions, session_specs


def test_sessions_wire_integrations_paths():
    cfg = AppConfig(
        sessions=SessionsConfig(
            dir="./.state",
            gsxt="gsxt_personal_session.json",
            aiqicha="./secrets/aiqicha_cookies.txt",
        )
    )
    assert cfg.integrations.gsxt.session_file.replace("\\", "/").endswith(
        ".state/gsxt_personal_session.json"
    )
    assert cfg.integrations.playwright.cookie_file == "./secrets/aiqicha_cookies.txt"


def test_list_sessions_reports_gsxt(tmp_path: Path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    state = root / ".state"
    state.mkdir()
    session = state / "gsxt_personal_session.json"
    session.write_text(
        json.dumps({"cookies": {"JSESSIONID": "abc"}, "saved_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.chdir(root)
    cfg = AppConfig(
        sessions=SessionsConfig(dir="./.state", gsxt="gsxt_personal_session.json")
    )
    report = list_sessions(cfg)
    gsxt = next(i for i in report["items"] if i["name"] == "gsxt")
    assert gsxt["ready"] is True
    assert gsxt["cookie_count"] == 1


def test_import_gsxt_browser_array(tmp_path: Path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    monkeypatch.chdir(root)
    export = root / "export.json"
    export.write_text(
        json.dumps([{"name": "SECTOKEN", "value": "999"}]),
        encoding="utf-8",
    )
    cfg = AppConfig(sessions=SessionsConfig(dir="./.state", gsxt="gsxt.json"))
    result = import_session(cfg, "gsxt", from_file=export)
    assert result["ok"] is True
    specs = session_specs(cfg, root)
    gsxt_path = next(s.path for s in specs if s.name == "gsxt")
    assert gsxt_path.is_file()
    saved = json.loads(gsxt_path.read_text(encoding="utf-8"))
    assert saved["cookies"]["SECTOKEN"] == "999"
