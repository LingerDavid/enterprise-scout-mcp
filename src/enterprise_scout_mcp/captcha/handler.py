"""Captcha branch — classify signal, optional solver hook, rotate IP on trigger."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from enterprise_scout_mcp.models import CollectResult, ResultGrade
from enterprise_scout_mcp.transport.proxy_pool import ProxyPoolClient


class CaptchaStrategy(str, Enum):
    ROTATE_IP = "rotate_ip"
    SOLVER_API = "solver_api"
    MANUAL = "manual"
    ABORT = "abort"


@dataclass
class CaptchaAction:
    strategy: CaptchaStrategy
    message: str = ""
    retry: bool = False


class CaptchaHandler:
    def __init__(
        self,
        *,
        proxy_client: ProxyPoolClient | None = None,
        default_strategy: CaptchaStrategy = CaptchaStrategy.ROTATE_IP,
    ) -> None:
        self._proxy = proxy_client
        self._default = default_strategy

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
            return CaptchaAction(
                strategy=CaptchaStrategy.SOLVER_API,
                message="solver API hook not wired yet",
                retry=False,
            )

        return CaptchaAction(
            strategy=CaptchaStrategy.MANUAL,
            message=result.message or "captcha - manual intervention required",
            retry=False,
        )
