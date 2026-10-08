"""Captcha solver API clients (CapSolver / 2Captcha style) — architecture §验证码处理分支."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class SolverResult:
    ok: bool
    token: str = ""
    message: str = ""
    raw: dict[str, Any] | None = None


class CaptchaSolver(Protocol):
    def solve_recaptcha_v2(self, *, site_key: str, page_url: str) -> SolverResult: ...

    def solve_geetest_v4(self, *, captcha_id: str, page_url: str) -> SolverResult: ...


class CapSolverClient:
    """https://docs.capsolver.com — requires CAPSOLVER_API_KEY or config api_key."""

    def __init__(self, api_key: str, *, base_url: str = "https://api.capsolver.com", timeout: float = 60.0) -> None:
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _create_and_poll(self, task: dict[str, Any]) -> SolverResult:
        if not self._api_key:
            return SolverResult(ok=False, message="capsolver api_key missing")
        try:
            with httpx.Client(timeout=self._timeout) as client:
                created = client.post(
                    f"{self._base}/createTask",
                    json={"clientKey": self._api_key, "task": task},
                )
                created.raise_for_status()
                payload = created.json()
                if payload.get("errorId"):
                    return SolverResult(ok=False, message=str(payload.get("errorDescription") or payload), raw=payload)
                task_id = payload.get("taskId")
                if not task_id:
                    return SolverResult(ok=False, message="capsolver missing taskId", raw=payload)
                for _ in range(30):
                    polled = client.post(
                        f"{self._base}/getTaskResult",
                        json={"clientKey": self._api_key, "taskId": task_id},
                    )
                    polled.raise_for_status()
                    body = polled.json()
                    status = body.get("status")
                    if status == "ready":
                        solution = body.get("solution") or {}
                        token = str(
                            solution.get("gRecaptchaResponse")
                            or solution.get("token")
                            or solution.get("captchaOutput")
                            or ""
                        )
                        return SolverResult(ok=bool(token), token=token, message="ok", raw=body)
                    if status == "failed" or body.get("errorId"):
                        return SolverResult(ok=False, message=str(body.get("errorDescription") or body), raw=body)
                    import time

                    time.sleep(2.0)
                return SolverResult(ok=False, message="capsolver poll timeout")
        except httpx.HTTPError as exc:
            return SolverResult(ok=False, message=str(exc))

    def solve_recaptcha_v2(self, *, site_key: str, page_url: str) -> SolverResult:
        return self._create_and_poll(
            {"type": "ReCaptchaV2TaskProxyLess", "websiteURL": page_url, "websiteKey": site_key}
        )

    def solve_geetest_v4(self, *, captcha_id: str, page_url: str) -> SolverResult:
        return self._create_and_poll(
            {
                "type": "GeeTestTaskProxyLess",
                "websiteURL": page_url,
                "captchaId": captcha_id,
                "version": 4,
            }
        )


def build_solver(provider: str, api_key: str) -> CaptchaSolver | None:
    provider = (provider or "").strip().lower()
    if not api_key:
        return None
    if provider in ("capsolver", "cap-solver"):
        return CapSolverClient(api_key)
    return None
