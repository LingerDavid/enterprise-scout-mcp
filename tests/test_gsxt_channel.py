"""GSXT channel without live network."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from enterprise_scout_mcp.channels.official.gsxt import GsxtOfficialChannel
from enterprise_scout_mcp.config import GsxtConfig
from enterprise_scout_mcp.models import CollectTask, Dimension, PersonaProfile, Platform, ResultGrade, SourceTier


def _persona() -> PersonaProfile:
    return PersonaProfile(id="p1", device={}, network={}, behavior={})


def test_gsxt_no_session_auth_expired(tmp_path: Path):
    cfg = GsxtConfig(session_file=str(tmp_path / "missing.json"))
    ch = GsxtOfficialChannel(cfg, state_dir=tmp_path)
    try:
        task = CollectTask(
            keyword="苏州挚途",
            platform=Platform.GSXT,
            dimensions=(Dimension.REGISTRY,),
            prefer_tier=SourceTier.L1,
            fields=("enterprise_info",),
        )
        result = ch.collect(task, _persona())
        assert result.grade == ResultGrade.AUTH_EXPIRED
        assert not ch.available()
    finally:
        ch.close()


def test_gsxt_collect_ok_with_mock(tmp_path: Path):
    session = tmp_path / "gsxt_personal_session.json"
    session.write_text(
        json.dumps({"cookies": {"token": "abc123"}}),
        encoding="utf-8",
    )
    cfg = GsxtConfig(session_file=str(session))
    ch = GsxtOfficialChannel(cfg, state_dir=tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"data":[{"entName":"Acme","uniscId":"91110000000000000X"}]}'
    mock_resp.json.return_value = {
        "data": [{"entName": "Acme", "uniscId": "91110000000000000X"}],
    }
    try:
        assert ch.available()
        with patch.object(ch._client, "post", return_value=mock_resp):
            task = CollectTask(
                keyword="Acme",
                platform=Platform.GSXT,
                dimensions=(Dimension.REGISTRY,),
                fields=("enterprise_info",),
            )
            result = ch.collect(task, _persona())
        assert result.grade == ResultGrade.OK
        assert result.data["enterprise_info"][0]["credit_code"] == "91110000000000000X"
        assert result.source_tier == SourceTier.L1
    finally:
        ch.close()
