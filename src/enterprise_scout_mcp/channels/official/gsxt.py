"""L1 GSXT registry channel — personal session + JSL/CT warmup + search API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from enterprise_scout_mcp.channels.base import CollectionChannel
from enterprise_scout_mcp.channels.official.parse import classify_response_text, parse_search_payload
from enterprise_scout_mcp.config import GsxtConfig, resolve_project_root
from enterprise_scout_mcp.integrations.gsxt_jsl import is_ct_challenge, is_jsl_challenge, pass_jsl_challenge
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
        self._index_url = config.base_url.rstrip("/") + "/index.html"
        self._client = httpx.Client(
            timeout=config.timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": config.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": self._index_url,
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

    def _persist_cookies(self, cookies: dict[str, str], note: str) -> None:
        save_session(self._session_path, cookies, note=note)

    def available(self) -> bool:
        if not self._config.enabled:
            return False
        if self._config.session_mode == "personal":
            return bool(self._session_cookies())
        return True

    def _warmup_browser(self, cookies: dict[str, str]) -> dict[str, str] | None:
        if not self._config.browser_warmup_on_ct:
            return None
        try:
            from enterprise_scout_mcp.integrations.gsxt_warmup import browser_warmup_cookies
        except ImportError:
            return None
        try:
            data_dir = Path(self._config.browser_user_data_dir)
            if not data_dir.is_absolute():
                data_dir = resolve_project_root() / data_dir
            fresh = browser_warmup_cookies(
                index_url=self._index_url,
                wait_seconds=self._config.browser_warmup_wait_seconds,
                user_data_dir=data_dir,
                existing=cookies,
            )
        except Exception:  # noqa: BLE001 — fall back to L2
            return None
        if fresh:
            self._persist_cookies(fresh, note="browser warmup after CT challenge")
        return fresh or None

    def _prepare_session(self, cookies: dict[str, str]) -> bool:
        return pass_jsl_challenge(
            self._client,
            page_url=self._index_url,
            cookies=cookies,
            user_agent=self._config.user_agent,
        )

    def _post_search(self, task: CollectTask, cookies: dict[str, str]) -> httpx.Response:
        body: dict[str, Any] = {
            self._config.search_keyword_field: task.keyword,
            "pageSize": 10,
            "pageNum": 1,
        }
        return self._client.post(
            self._config.search_url,
            json=body,
            cookies=cookies,
        )

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

        self._prepare_session(cookies)
        try:
            r = self._post_search(task, cookies)
            text = r.text
        except httpx.HTTPError as exc:
            base.message = str(exc)
            return base

        if is_ct_challenge(r.status_code, text):
            warmed = self._warmup_browser(cookies)
            if warmed:
                cookies.update(warmed)
                self._prepare_session(cookies)
                try:
                    r = self._post_search(task, cookies)
                    text = r.text
                except httpx.HTTPError as exc:
                    base.message = f"CT warmup ok but search failed: {exc}"
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
                base.message = (
                    "GSXT JSL challenge — install Node.js or run "
                    "escout sync-gsxt-session --warmup"
                )
                return base
        if hint == "ct_challenge":
            base.grade = ResultGrade.CAPTCHA
            base.message = (
                "GSXT CT/瑞数 challenge — export cookies after visiting www.gsxt.gov.cn "
                "or run escout sync-gsxt-session --warmup (pip install -e '.[browser]')"
            )
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
            base.message = "GSXT blocked IP — use personal login session or retry later"
            return base

        parsed: Any
        try:
            parsed = r.json()
        except json.JSONDecodeError:
            parsed = text

        row = parse_search_payload(parsed)
        if not row or not (row.get("name") or row.get("credit_code")):
            if is_jsl_challenge(r.status_code, text):
                base.grade = ResultGrade.CAPTCHA
                base.message = "GSXT JSL challenge on search — install Node.js or use --warmup"
            else:
                base.grade = ResultGrade.PARTIAL if r.status_code == 200 else ResultGrade.ERROR
                base.message = f"GSXT search returned no registry row (HTTP {r.status_code})"
            base.data = {"raw": parsed if isinstance(parsed, dict) else {"text": text[:2000]}}
            return base

        self._persist_cookies(cookies, note="post-search cookie refresh")
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
