"""Playwright channel - DB first, httpx fetch, nodriver on captcha."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.config import PlaywrightConfig
from enterprise_scout_mcp.integrations.aiqicha_db import lookup_company
from enterprise_scout_mcp.integrations.aiqicha_runner import fetch_with_fallback
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    PersonaProfile,
    Platform,
    ResultGrade,
)
from enterprise_scout_mcp.channels.base import CollectionChannel


class PlaywrightAiqichaChannel(CollectionChannel):
    kind = ChannelKind.PLAYWRIGHT.value

    def __init__(self, config: PlaywrightConfig, *, project_root: Path | None = None) -> None:
        self._config = config
        self._root = project_root or Path(__file__).resolve().parents[3]

    def _resolve(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self._root / p

    def _db_path(self) -> Path:
        return self._resolve(self._config.companies_db)

    def _cookie_file(self) -> Path | None:
        path = self._resolve(self._config.cookie_file)
        return path if path.is_file() else None

    def available(self) -> bool:
        if not self._config.enabled:
            return False
        if self._db_path().is_file():
            return True
        if not self._config.fetch_on_miss:
            return False
        return self._resolve(self._config.fetch_script).is_file()

    def _result_from_payload(
        self,
        task: CollectTask,
        persona: PersonaProfile,
        payload: dict,
        db_path: Path,
    ) -> CollectResult:
        status = str(payload.get("status", "error"))
        if status == "captcha":
            return CollectResult(
                task=task,
                channel=ChannelKind.PLAYWRIGHT,
                grade=ResultGrade.CAPTCHA,
                message="aiqicha captcha (httpx and nodriver failed)",
                persona_id=persona.id,
            )
        if status == "ok" and payload.get("company"):
            company = payload["company"]
            hit = lookup_company(task.keyword, db_path) if db_path.is_file() else None
            data = hit if hit else company
            source = str(payload.get("source", "fetch"))
            return CollectResult(
                task=task,
                channel=ChannelKind.PLAYWRIGHT,
                grade=ResultGrade.OK,
                data=data if isinstance(data, dict) else company,
                message=f"fetched via {source}",
                persona_id=persona.id,
            )
        return CollectResult(
            task=task,
            channel=ChannelKind.PLAYWRIGHT,
            grade=ResultGrade.PARTIAL if status == "not_found" else ResultGrade.ERROR,
            message=str(payload.get("message") or status),
            persona_id=persona.id,
        )

    def collect(self, task: CollectTask, persona: PersonaProfile) -> CollectResult:
        if task.platform != Platform.AIQICHA:
            return CollectResult(
                task=task,
                channel=ChannelKind.PLAYWRIGHT,
                grade=ResultGrade.ERROR,
                message="Playwright channel currently wired for aiqicha only",
                persona_id=persona.id,
            )

        db_path = self._db_path()
        if db_path.is_file():
            hit = lookup_company(task.keyword, db_path)
            if hit:
                return CollectResult(
                    task=task,
                    channel=ChannelKind.PLAYWRIGHT,
                    grade=ResultGrade.OK,
                    data=hit,
                    message="hit aiqicha_scraper companies.db",
                    persona_id=persona.id,
                )

        if not self._config.fetch_on_miss:
            return CollectResult(
                task=task,
                channel=ChannelKind.PLAYWRIGHT,
                grade=ResultGrade.PARTIAL,
                message=f"no row in {db_path}; fetch_on_miss disabled",
                persona_id=persona.id,
            )

        nodriver_script = self._resolve(self._config.nodriver_script)
        payload = fetch_with_fallback(
            task.keyword,
            db_path=db_path,
            cookie_file=self._cookie_file(),
            httpx_script=self._resolve(self._config.fetch_script),
            nodriver_script=nodriver_script,
            nodriver_enabled=self._config.nodriver_on_captcha,
            nodriver_user_data_dir=self._resolve(self._config.nodriver_user_data_dir),
            timeout_seconds=self._config.fetch_timeout_seconds,
        )
        return self._result_from_payload(task, persona, payload, db_path)
