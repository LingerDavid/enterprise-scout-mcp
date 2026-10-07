"""Playwright channel - aiqicha DB bridge (aiqicha_scraper search-before-network)."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.config import PlaywrightConfig
from enterprise_scout_mcp.integrations.aiqicha_db import lookup_company
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

    def __init__(self, config: PlaywrightConfig) -> None:
        self._config = config

    def available(self) -> bool:
        if not self._config.enabled:
            return False
        db = Path(self._config.companies_db)
        return db.is_file()

    def collect(self, task: CollectTask, persona: PersonaProfile) -> CollectResult:
        if task.platform != Platform.AIQICHA:
            return CollectResult(
                task=task,
                channel=ChannelKind.PLAYWRIGHT,
                grade=ResultGrade.ERROR,
                message="Playwright channel currently wired for aiqicha only",
                persona_id=persona.id,
            )

        db_path = Path(self._config.companies_db)
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

        return CollectResult(
            task=task,
            channel=ChannelKind.PLAYWRIGHT,
            grade=ResultGrade.PARTIAL,
            message=(
                f"no row in {db_path}; run aiqicha_scraper or enable ENScan channel"
            ),
            persona_id=persona.id,
        )
