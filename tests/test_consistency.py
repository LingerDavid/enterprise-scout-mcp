"""Environment consistency — timezone / OS / language."""

from __future__ import annotations

from enterprise_scout_mcp.consistency.validator import EnvironmentValidator, ua_implies_os
from enterprise_scout_mcp.models import PersonaProfile


def _persona(**device_extra) -> PersonaProfile:
    device = {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "locale": "zh-CN",
        "language": "zh",
        "timezone": "Asia/Shanghai",
        "os": "windows",
        **device_extra,
    }
    return PersonaProfile(
        id="test",
        device=device,
        network={"country": "CN", "tls_impersonate": "chrome131"},
        behavior={},
    )


def test_ok_when_headers_match() -> None:
    p = _persona()
    report = EnvironmentValidator().validate(
        p,
        outbound_headers={
            "User-Agent": p.user_agent,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Sec-CH-UA-Platform": '"Windows"',
        },
        tls_profile="chrome131",
        host_timezone="Asia/Shanghai",
        host_os="windows",
    )
    assert report.ok
    assert report.violations == ()


def test_timezone_invalid_shape() -> None:
    p = _persona(timezone="NotAZone")
    report = EnvironmentValidator().validate(p)
    assert not report.ok
    assert any("timezone" in v for v in report.violations)


def test_os_ua_mismatch() -> None:
    p = _persona(os="macos")
    report = EnvironmentValidator().validate(
        p,
        outbound_headers={"User-Agent": p.user_agent},
    )
    assert not report.ok
    assert any("OS hint" in v for v in report.violations)


def test_language_mismatch() -> None:
    p = _persona(language="en")
    report = EnvironmentValidator().validate(
        p,
        outbound_headers={"Accept-Language": "zh-CN,zh;q=0.9"},
    )
    assert not report.ok
    assert any("language" in v for v in report.violations)


def test_ua_implies_os() -> None:
    assert ua_implies_os("Mozilla/5.0 (Windows NT 10.0; Win64; x64)") == "windows"
    assert ua_implies_os("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15)") == "macos"
