"""GSXT search response parsing."""

from __future__ import annotations

from enterprise_scout_mcp.channels.official.parse import classify_response_text, parse_search_payload


def test_parse_search_json_list():
    payload = {
        "data": [
            {"entName": "苏州挚途科技有限公司", "uniscId": "91320594MA1XXXXXX"},
        ]
    }
    row = parse_search_payload(payload)
    assert row is not None
    assert row["name"] == "苏州挚途科技有限公司"
    assert row["credit_code"] == "91320594MA1XXXXXX"


def test_classify_auth_expired():
    assert classify_response_text("请访问 shiming 实名注册/登录后再进行访问") == "auth_expired"


def test_classify_captcha():
    assert classify_response_text("请完成 geetest 验证码") == "captcha"
