"""L1 GSXT registry channel — personal session + public search API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from enterprise_scout_mcp.channels.base import CollectionChannel
from enterprise_scout_mcp.channels.official.parse import classify_response_text, parse_search_payload
from enterprise_scout_mcp.config import GsxtConfig, resolve_project_root
from enterprise_scout_mcp.integrations.gsxt_session import load_session
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    PersonaProfile,
    ResultGrade,
    SourceTier,
)
from enterprise_scout_mcp.transport.egress import EgressContext


class GsxtOfficialChannel(CollectionChannel):
    kind = ChannelKind.GSXT_OFFICIAL.value

    def __init__(self, config: GsxtConfig, *, state_dir: Path) -> None:
        self._config = config
        root = resolve_project_root()
        session_path = Path(config.session_file)
        if not session_path.is_absolute():
            session_path = root / session_path
        self._session_path = session_path
        self._client = httpx.Client(
            timeout=config.timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": config.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": config.base_url.rstrip("/") + "/index.html",
                "Origin": config.base_url.rstrip("/"),
            },
        )

    def close(self) -> None:
        self._client.close()

    def _session_cookies(self) -> dict[str, str]:
        raw = load_session(self._session_path)
        if not raw:
            return {}
        cookies = raw.get("cookies")
        if isinstance(cookies, dict):
            return {str(k): str(v) for k, v in cookies.items()}
        return {}

    def available(self) -> bool:
        if not self._config.enabled:
            return False
        if self._config.session_mode == "personal":
            return bool(self._session_cookies())
        return True

    def collect(
        self,
        task: CollectTask,
        persona: PersonaProfile,
        *,
        egress: EgressContext | None = None,
    ) -> CollectResult:
        _ = persona, egress
        base = CollectResult(
            task=task,
            channel=ChannelKind.GSXT_OFFICIAL,
            grade=ResultGrade.ERROR,
            persona_id=persona.id,
            source_tier=SourceTier.L1,
            dimension=task.primary_dimension,
        )

        cookies = self._session_cookies()
        if self._config.session_mode == "personal" and not cookies:
            base.grade = ResultGrade.AUTH_EXPIRED
            base.message = (
                "GSXT personal session missing — login at shiming.gsxt.gov.cn then "
                "escout sync-gsxt-session --from-file cookies.json"
            )
            return base

        url = self._config.search_url
        body: dict[str, Any] = {
            self._config.search_keyword_field: task.keyword,
            "pageSize": 10,
            "pageNum": 1,
        }

        try:
            r = self._client.post(url, json=body, cookies=cookies)
            text = r.text
        except httpx.HTTPError as exc:
            base.message = str(exc)
            return base

        hint = classify_response_text(text)
        if hint == "auth_expired":
            base.grade = ResultGrade.AUTH_EXPIRED
            base.message = "GSXT session expired — re-run sync-gsxt-session"
            return base
        if hint == "captcha":
            base.grade = ResultGrade.CAPTCHA
            base.message = "GSXT captcha — complete in browser then refresh session"
            return base
        if hint == "blocked":
            base.grade = ResultGrade.BLOCKED
            base.message = "GSXT blocked IP — use personal login session or retry later"
            return base

        parsed: Any
        try:
            parsed = r.json()
        except json.JSONDecodeError:
            parsed = text

        row = parse_search_payload(parsed)
        if not row or not (row.get("name") or row.get("credit_code")):
            base.grade = ResultGrade.PARTIAL if r.status_code == 200 else ResultGrade.ERROR
            base.message = f"GSXT search returned no registry row (HTTP {r.status_code})"
            base.data = {"raw": parsed if isinstance(parsed, dict) else {"text": text[:2000]}}
            return base

        data = {
            "enterprise_info": [
                {
                    "name": row.get("name") or task.keyword,
                    "credit_code": row.get("credit_code") or "",
                    "reg_code": row.get("reg_code") or row.get("credit_code") or "",
                }
            ],
            "source": "gsxt_official",
            "source_tier": SourceTier.L1.value,
        }
        return CollectResult(
            task=task,
            channel=ChannelKind.GSXT_OFFICIAL,
            grade=ResultGrade.OK,
            data=data,
            message="ok",
            persona_id=persona.id,
            source_tier=SourceTier.L1,
            dimension=task.primary_dimension,
        )
