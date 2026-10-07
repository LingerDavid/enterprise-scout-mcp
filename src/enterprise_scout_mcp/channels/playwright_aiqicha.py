"""Playwright channel - aiqicha DB first, httpx fetch fallback on miss."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.config import PlaywrightConfig
from enterprise_scout_mcp.integrations.aiqicha_db import lookup_company
from enterprise_scout_mcp.integrations.aiqicha_runner import fetch_one
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

    def _db_path(self) -> Path:
        p = Path(self._config.companies_db)
        return p if p.is_absolute() else self._root / p

    def _fetch_script(self) -> Path:
        p = Path(self._config.fetch_script)
        return p if p.is_absolute() else self._root / p

    def _cookie_file(self) -> Path | None:
        p = Path(self._config.cookie_file)
        path = p if p.is_absolute() else self._root / p
        return path if path.is_file() else None

    def available(self) -> bool:
        if not self._config.enabled:
            return False
        if self._db_path().is_file():
            return True
        return self._config.fetch_on_miss and self._fetch_script().is_file()

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
        hit = lookup_company(task.keyword, db_path) if db_path.is_file() else None
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

        payload = fetch_one(
            task.keyword,
            db_path=db_path,
            cookie_file=self._cookie_file(),
            script_path=self._fetch_script(),
            timeout_seconds=self._config.fetch_timeout_seconds,
        )
        status = str(payload.get("status", "error"))
        if status == "captcha":
            return CollectResult(
                task=task,
                channel=ChannelKind.PLAYWRIGHT,
                grade=ResultGrade.CAPTCHA,
                message="aiqicha captcha during fetch",
                persona_id=persona.id,
            )
        if status == "ok" and payload.get("company"):
            company = payload["company"]
            hit = lookup_company(task.keyword, db_path) or company
            return CollectResult(
                task=task,
                channel=ChannelKind.PLAYWRIGHT,
                grade=ResultGrade.OK,
                data=hit if isinstance(hit, dict) else company,
                message="fetched via aiqicha_fetch_one",
                persona_id=persona.id,
            )

        return CollectResult(
            task=task,
            channel=ChannelKind.PLAYWRIGHT,
            grade=ResultGrade.PARTIAL if status == "not_found" else ResultGrade.ERROR,
            message=str(payload.get("message") or status),
            persona_id=persona.id,
        )
