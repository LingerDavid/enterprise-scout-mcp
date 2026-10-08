"""GSXT session import formats."""

from __future__ import annotations

import json
from pathlib import Path

from enterprise_scout_mcp.integrations.gsxt_session import cookies_from_export, import_session_file


def test_cookies_from_browser_array():
    raw = [
        {"name": "JSESSIONID", "value": "abc", "domain": "shiming.gsxt.gov.cn"},
        {"name": "", "value": "HttpOnly", "domain": "shiming.gsxt.gov.cn"},
        {"name": "CT_1f7ba0eb8", "value": "deadbeef", "domain": ".gsxt.gov.cn"},
    ]
    cookies = cookies_from_export(raw)
    assert cookies == {"JSESSIONID": "abc", "CT_1f7ba0eb8": "deadbeef"}


def test_import_session_file_from_array(tmp_path: Path):
    src = tmp_path / "export.json"
    src.write_text(
        json.dumps([{"name": "SECTOKEN", "value": "123"}]),
        encoding="utf-8",
    )
    dest = tmp_path / "session.json"
    preview = import_session_file(src, dest)
    assert preview["SECTOKEN"] == "123"
    saved = json.loads(dest.read_text(encoding="utf-8"))
    assert saved["cookies"]["SECTOKEN"] == "123"
