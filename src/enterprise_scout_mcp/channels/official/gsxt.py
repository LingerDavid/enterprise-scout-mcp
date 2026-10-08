"""L1 GSXT registry — browser in-page search (CT/瑞数 safe) with optional httpx API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from enterprise_scout_mcp.channels.base import CollectionChannel
from enterprise_scout_mcp.channels.official.parse import classify_response_text, parse_search_payload
from enterprise_scout_mcp.config import GsxtConfig, resolve_project_root
from enterprise_scout_mcp.integrations.gsxt_browser import search_registry_browser
from enterprise_scout_mcp.integrations.gsxt_jsl import is_ct_challenge, is_jsl_challenge, pass_jsl_challenge
from enterprise_scout_mcp.integrations.gsxt_transport import resolve_gsxt_proxy
from enterprise_scout_mcp.integrations.gsxt_session import load_session, save_session
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
        self._root = root
        self._index_url = config.base_url.rstrip("/") + "/index.html"
        self._user_data_dir = Path(config.browser_user_data_dir)
        if not self._user_data_dir.is_absolute():
            self._user_data_dir = root / self._user_data_dir
        self._proxy_url: str | None = None
        self._client = self._make_client(None)

    def _make_client(self, proxy_url: str | None) -> httpx.Client:
        kwargs: dict[str, Any] = {
            "timeout": self._config.timeout_seconds,
            "follow_redirects": True,
            "headers": {
                "User-Agent": self._config.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": self._index_url,
                "Origin": self._config.base_url.rstrip("/"),
            },
        }
        if proxy_url:
            kwargs["proxy"] = proxy_url
        return httpx.Client(**kwargs)

    def _ensure_client_proxy(self, proxy_url: str | None) -> None:
        if proxy_url == self._proxy_url:
            return
        self._client.close()
        self._client = self._make_client(proxy_url)
        self._proxy_url = proxy_url

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

    def _persist_cookies(self, cookies: dict[str, str], note: str) -> None:
        if cookies:
            save_session(self._session_path, cookies, note=note)

    def available(self) -> bool:
        if not self._config.enabled:
            return False
        if self._config.session_mode == "personal":
            return bool(self._session_cookies())
        return True

    def _base_result(self, task: CollectTask, persona: PersonaProfile) -> CollectResult:
        return CollectResult(
            task=task,
            channel=ChannelKind.GSXT_OFFICIAL,
            grade=ResultGrade.ERROR,
            persona_id=persona.id,
            source_tier=SourceTier.L1,
            dimension=task.primary_dimension,
        )

    def _ok_result(
        self,
        task: CollectTask,
        persona: PersonaProfile,
        row: dict[str, str],
        *,
        via: str,
    ) -> CollectResult:
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
            "search_via": via,
        }
        return CollectResult(
            task=task,
            channel=ChannelKind.GSXT_OFFICIAL,
            grade=ResultGrade.OK,
            data=data,
            message=via if via.startswith("ok") else f"ok ({via})",
            persona_id=persona.id,
            source_tier=SourceTier.L1,
            dimension=task.primary_dimension,
        )

    def _collect_browser(
        self,
        task: CollectTask,
        persona: PersonaProfile,
        cookies: dict[str, str],
        *,
        proxy_url: str | None = None,
    ) -> CollectResult:
        base = self._base_result(task, persona)
        result = search_registry_browser(
            task.keyword,
            config=self._config,
            cookies=cookies,
            user_data_dir=self._user_data_dir,
            index_url=self._index_url,
            proxy_url=proxy_url,
        )
        if result.cookies:
            self._persist_cookies(result.cookies, note="browser search cookie refresh")
        if result.ok and result.row:
            return self._ok_result(task, persona, result.row, via="browser")
        base.grade = ResultGrade.CAPTCHA
        base.message = result.message or "GSXT browser search failed"
        if result.html_snippet:
            base.data = {"raw": {"html": result.html_snippet}}
        return base

    def _post_search(self, task: CollectTask, cookies: dict[str, str]) -> httpx.Response:
        body: dict[str, Any] = {
            self._config.search_keyword_field: task.keyword,
            "pageSize": 10,
            "pageNum": 1,
        }
        return self._client.post(self._config.search_url, json=body, cookies=cookies)

    def _collect_api(
        self,
        task: CollectTask,
        persona: PersonaProfile,
        cookies: dict[str, str],
        *,
        proxy_url: str | None = None,
    ) -> CollectResult:
        base = self._base_result(task, persona)
        self._prepare_session(cookies)
        try:
            r = self._post_search(task, cookies)
            text = r.text
        except httpx.HTTPError as exc:
            base.message = str(exc)
            return base

        hint = classify_response_text(text, status_code=r.status_code)
        if hint == "jsl_challenge":
            if self._prepare_session(cookies):
                self._persist_cookies(cookies, note="jsl clearance refresh")
                try:
                    r = self._post_search(task, cookies)
                    text = r.text
                    hint = classify_response_text(text, status_code=r.status_code)
                except httpx.HTTPError as exc:
                    base.message = f"JSL retry failed: {exc}"
                    return base
            else:
                base.grade = ResultGrade.CAPTCHA
                base.message = "GSXT JSL challenge — install Node.js"
                return base
        if hint == "ct_challenge":
            base.grade = ResultGrade.CAPTCHA
            base.message = "GSXT CT/瑞数 on API — use search_mode=browser (default)"
            return base
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
            base.message = "GSXT blocked IP"
            return base

        parsed: Any
        try:
            parsed = r.json()
        except json.JSONDecodeError:
            parsed = text

        row = parse_search_payload(parsed)
        if not row or not (row.get("name") or row.get("credit_code")):
            base.grade = ResultGrade.PARTIAL if r.status_code == 200 else ResultGrade.ERROR
            base.message = f"GSXT API returned no registry row (HTTP {r.status_code})"
            base.data = {"raw": parsed if isinstance(parsed, dict) else {"text": text[:2000]}}
            return base

        self._persist_cookies(cookies, note="post-api cookie refresh")
        return self._ok_result(task, persona, row, via="api")

    def _prepare_session(self, cookies: dict[str, str]) -> bool:
        return pass_jsl_challenge(
            self._client,
            page_url=self._index_url,
            cookies=cookies,
            user_agent=self._config.user_agent,
        )

    def collect(
        self,
        task: CollectTask,
        persona: PersonaProfile,
        *,
        egress: EgressContext | None = None,
    ) -> CollectResult:
        proxy_url = resolve_gsxt_proxy(self._config, egress)
        self._ensure_client_proxy(proxy_url)
        base = self._base_result(task, persona)
        cookies = self._session_cookies()
        if self._config.session_mode == "personal" and not cookies:
            base.grade = ResultGrade.AUTH_EXPIRED
            base.message = (
                "GSXT personal session missing — login at shiming.gsxt.gov.cn then "
                "escout sessions import gsxt --from-file cookies.json"
            )
            return base

        mode = (self._config.search_mode or "browser").lower()
        if mode in ("browser", "auto"):
            browser_result = self._collect_browser(task, persona, cookies, proxy_url=proxy_url)
            if browser_result.grade == ResultGrade.OK or mode == "browser":
                return browser_result
        return self._collect_api(task, persona, cookies, proxy_url=proxy_url)
