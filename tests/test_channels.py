"""Channel unit tests (mocked HTTP, no live network)."""

from __future__ import annotations

from hashlib import md5
from unittest.mock import MagicMock, patch

import httpx

from enterprise_scout_mcp.channels.ensan_go import EnsanGoChannel
from enterprise_scout_mcp.channels.handaas_api import HandaasChannel
from enterprise_scout_mcp.config import EnsanGoConfig, HandaasConfig
from enterprise_scout_mcp.models import CollectTask, PersonaProfile, Platform, ResultGrade


def _persona() -> PersonaProfile:
    return PersonaProfile(id="t", device={}, network={}, behavior={})


def test_ensan_go_detects_captcha() -> None:
    channel = EnsanGoChannel(EnsanGoConfig(enabled=True))
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 400, "message": "需要验证码", "data": {}}
    with patch.object(channel._client, "get", return_value=mock_resp):
        result = channel.collect(
            CollectTask(keyword="test", platform=Platform.AIQICHA),
            _persona(),
        )
    assert result.grade == ResultGrade.CAPTCHA


def test_handaas_signing_and_search() -> None:
    cfg = HandaasConfig(
        enabled=True,
        integrator_id="int1",
        secret_id="sid",
        secret_key="skey",
    )
    channel = HandaasChannel(cfg)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": {"total": 1, "resultList": [{"name": "Co"}]}}
    captured: dict = {}

    def fake_post(url: str, data: dict) -> MagicMock:
        captured["url"] = url
        captured["data"] = data
        return mock_resp

    channel._client.post = fake_post  # type: ignore[method-assign]

    result = channel.collect(
        CollectTask(keyword="小米", platform=Platform.HANDAAS, depth=0),
        _persona(),
    )

    assert result.grade == ResultGrade.OK
    assert captured["data"]["product_id"] == "enterprise_get_keyword_search"
    keys = sorted(captured["data"].keys())
    sign_src = "".join(str(captured["data"][k]) for k in keys if k != "signature") + "skey"
    assert captured["data"]["signature"] == md5(sign_src.encode()).hexdigest()


def test_handaas_base_info_when_depth_positive() -> None:
    cfg = HandaasConfig(
        enabled=True,
        integrator_id="int1",
        secret_id="sid",
        secret_key="skey",
    )
    channel = HandaasChannel(cfg)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": {"name": "Co"}}
    captured: dict = {}

    def fake_post(url: str, data: dict) -> MagicMock:
        captured["data"] = data
        return mock_resp

    channel._client.post = fake_post  # type: ignore[method-assign]

    channel.collect(
        CollectTask(keyword="小米科技", platform=Platform.HANDAAS, depth=1),
        _persona(),
    )
    assert captured["data"]["product_id"] == "enterprise_get_enterprise_base_info"


def test_handaas_http_error() -> None:
    channel = HandaasChannel(
        HandaasConfig(enabled=True, integrator_id="i", secret_id="s", secret_key="k")
    )
    with patch.object(channel._client, "post", side_effect=httpx.ConnectError("refused")):
        result = channel.collect(
            CollectTask(keyword="x", platform=Platform.HANDAAS),
            _persona(),
        )
    assert result.grade == ResultGrade.ERROR
