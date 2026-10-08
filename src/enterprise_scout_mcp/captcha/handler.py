"""Captcha branch — classify signal, solver API, OpenCV slider, rotate IP."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from enterprise_scout_mcp.captcha.opencv_slider import SliderGapResult, detect_slider_gap, opencv_available
from enterprise_scout_mcp.captcha.solver import CaptchaSolver, SolverResult, build_solver
from enterprise_scout_mcp.models import CollectResult, ResultGrade
from enterprise_scout_mcp.transport.proxy_pool import ProxyPoolClient


class CaptchaStrategy(str, Enum):
    ROTATE_IP = "rotate_ip"
    SOLVER_API = "solver_api"
    OPENCV_SLIDER = "opencv_slider"
    MANUAL = "manual"
    ABORT = "abort"


@dataclass
class CaptchaAction:
    strategy: CaptchaStrategy
    message: str = ""
    retry: bool = False
    token: str = ""
    slider_offset_px: int = 0


class CaptchaHandler:
    def __init__(
        self,
        *,
        proxy_client: ProxyPoolClient | None = None,
        default_strategy: CaptchaStrategy = CaptchaStrategy.ROTATE_IP,
        solver: CaptchaSolver | None = None,
    ) -> None:
        self._proxy = proxy_client
        self._default = default_strategy
        self._solver = solver

    def handle(self, result: CollectResult, *, bad_proxy: str | None = None) -> CaptchaAction:
        if result.grade != ResultGrade.CAPTCHA:
            return CaptchaAction(strategy=CaptchaStrategy.ABORT, message="not a captcha result")

        if self._default == CaptchaStrategy.ROTATE_IP and self._proxy and bad_proxy:
            try:
                self._proxy.delete(bad_proxy)
            except Exception as exc:  # noqa: BLE001 - best-effort pool hygiene
                return CaptchaAction(
                    strategy=CaptchaStrategy.MANUAL,
                    message=f"proxy delete failed: {exc}",
                    retry=False,
                )
            return CaptchaAction(
                strategy=CaptchaStrategy.ROTATE_IP,
                message="proxy rotated; retry with new egress",
                retry=True,
            )

        if self._default == CaptchaStrategy.SOLVER_API:
            if self._solver is None:
                return CaptchaAction(
                    strategy=CaptchaStrategy.SOLVER_API,
                    message="solver API configured but no api_key / provider",
                    retry=False,
                )
            return CaptchaAction(
                strategy=CaptchaStrategy.SOLVER_API,
                message="solver ready — call solve_* with site challenge params",
                retry=False,
            )

        if self._default == CaptchaStrategy.OPENCV_SLIDER:
            if not opencv_available():
                return CaptchaAction(
                    strategy=CaptchaStrategy.OPENCV_SLIDER,
                    message="opencv not installed — pip install -e '.[captcha]'",
                    retry=False,
                )
            return CaptchaAction(
                strategy=CaptchaStrategy.OPENCV_SLIDER,
                message="opencv slider ready — call solve_slider with background/template bytes",
                retry=False,
            )

        return CaptchaAction(
            strategy=CaptchaStrategy.MANUAL,
            message=result.message or "captcha - manual intervention required",
            retry=False,
        )

    def solve_recaptcha_v2(self, *, site_key: str, page_url: str) -> SolverResult:
        if self._solver is None:
            return SolverResult(ok=False, message="no solver configured")
        return self._solver.solve_recaptcha_v2(site_key=site_key, page_url=page_url)

    def solve_geetest_v4(self, *, captcha_id: str, page_url: str) -> SolverResult:
        if self._solver is None:
            return SolverResult(ok=False, message="no solver configured")
        return self._solver.solve_geetest_v4(captcha_id=captcha_id, page_url=page_url)

    def solve_slider(self, background: Any, *, template: Any = None) -> SliderGapResult:
        return detect_slider_gap(background, template=template)


def strategy_from_name(name: str) -> CaptchaStrategy:
    key = (name or "rotate_ip").strip().lower()
    try:
        return CaptchaStrategy(key)
    except ValueError:
        return CaptchaStrategy.MANUAL


def build_captcha_handler(
    *,
    proxy_client: ProxyPoolClient | None,
    strategy: str = "rotate_ip",
    solver_provider: str = "",
    solver_api_key: str = "",
) -> CaptchaHandler:
    return CaptchaHandler(
        proxy_client=proxy_client,
        default_strategy=strategy_from_name(strategy),
        solver=build_solver(solver_provider, solver_api_key),
    )
