"""Captcha branch — strategy routing, solver factory, OpenCV hook."""

from __future__ import annotations

from unittest.mock import MagicMock

from enterprise_scout_mcp.captcha.handler import (
    CaptchaStrategy,
    build_captcha_handler,
    strategy_from_name,
)
from enterprise_scout_mcp.captcha.opencv_slider import detect_slider_gap, opencv_available
from enterprise_scout_mcp.captcha.solver import CapSolverClient, build_solver
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    Platform,
    ResultGrade,
)


def _captcha_result() -> CollectResult:
    return CollectResult(
        task=CollectTask(keyword="测试", platform=Platform.GSXT),
        channel=ChannelKind.GSXT_OFFICIAL,
        grade=ResultGrade.CAPTCHA,
        message="geetest",
    )


def test_strategy_from_name() -> None:
    assert strategy_from_name("rotate_ip") is CaptchaStrategy.ROTATE_IP
    assert strategy_from_name("solver_api") is CaptchaStrategy.SOLVER_API
    assert strategy_from_name("opencv_slider") is CaptchaStrategy.OPENCV_SLIDER
    assert strategy_from_name("unknown") is CaptchaStrategy.MANUAL


def test_rotate_ip_deletes_proxy() -> None:
    proxy = MagicMock()
    handler = build_captcha_handler(proxy_client=proxy, strategy="rotate_ip")
    action = handler.handle(_captcha_result(), bad_proxy="http://1.2.3.4:8080")
    assert action.strategy is CaptchaStrategy.ROTATE_IP
    assert action.retry is True
    proxy.delete.assert_called_once_with("http://1.2.3.4:8080")


def test_solver_api_without_key() -> None:
    handler = build_captcha_handler(
        proxy_client=None,
        strategy="solver_api",
        solver_provider="capsolver",
        solver_api_key="",
    )
    action = handler.handle(_captcha_result())
    assert action.strategy is CaptchaStrategy.SOLVER_API
    assert action.retry is False
    assert "api_key" in action.message or "no" in action.message.lower()


def test_build_solver_capsolver() -> None:
    solver = build_solver("capsolver", "test-key")
    assert isinstance(solver, CapSolverClient)


def test_build_solver_missing_key() -> None:
    assert build_solver("capsolver", "") is None


def test_opencv_slider_without_deps() -> None:
    if opencv_available():
        # With deps installed, empty bytes should fail decode cleanly
        result = detect_slider_gap(b"")
        assert result.ok is False
    else:
        result = detect_slider_gap(b"\x00\x01")
        assert result.ok is False
        assert "opencv" in result.message.lower()


def test_handler_solve_recaptcha_without_solver() -> None:
    handler = build_captcha_handler(proxy_client=None, strategy="manual")
    out = handler.solve_recaptcha_v2(site_key="k", page_url="https://example.com")
    assert out.ok is False
