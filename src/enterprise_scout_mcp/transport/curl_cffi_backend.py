"""Unified disguise egress via curl_cffi (Scrapling-style TLS impersonation)."""

from __future__ import annotations

from typing import Any

from enterprise_scout_mcp.models import PersonaProfile


class CurlCffiTransport:
    def __init__(self, impersonate: str = "chrome131") -> None:
        self._impersonate = impersonate
        self._session = None

    def _ensure_session(self) -> Any:
        if self._session is not None:
            return self._session
        try:
            from curl_cffi.requests import Session
        except ImportError as exc:
            raise RuntimeError(
                "curl_cffi not installed; pip install enterprise-scout-mcp[transport]"
            ) from exc
        self._session = Session(impersonate=self._impersonate)
        return self._session

    def build_headers(self, persona: PersonaProfile) -> dict[str, str]:
        headers = dict(persona.device.get("headers") or {})
        if persona.user_agent:
            headers.setdefault("User-Agent", persona.user_agent)
        headers.setdefault("Accept-Language", persona.locale)
        return headers

    def get(
        self,
        url: str,
        persona: PersonaProfile,
        *,
        proxy: str | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, str]:
        session = self._ensure_session()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        resp = session.get(
            url,
            headers=self.build_headers(persona),
            proxies=proxies,
            timeout=timeout,
        )
        return resp.status_code, resp.text
