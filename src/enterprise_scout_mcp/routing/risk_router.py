"""Risk-aware routing — ENScan-first for registry platforms (no scrape fallback)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from enterprise_scout_mcp.config import RoutingConfig
from enterprise_scout_mcp.models import (
    ChannelKind,
    ChannelStats,
    CollectTask,
    Platform,
)

if TYPE_CHECKING:
    from enterprise_scout_mcp.state.store import StateStore

STATE_FILE = "routing.json"

_REGISTRY_PLATFORMS = (
    Platform.AIQICHA,
    Platform.TIANYANCHA,
    Platform.KUAICHA,
    Platform.RISKBIRD,
)


class RiskAwareRouter:
    def __init__(self, config: RoutingConfig, store: StateStore | None = None) -> None:
        self._config = config
        self._store = store
        self._stats: dict[tuple[Platform, ChannelKind], ChannelStats] = {}
        self._load()

    def _load(self) -> None:
        if self._store is None:
            return
        raw = self._store.load(STATE_FILE)
        for row in raw.get("stats") or []:
            try:
                platform = Platform(row["platform"])
                channel = ChannelKind(row["channel"])
            except (KeyError, ValueError):
                continue
            self._stats[(platform, channel)] = ChannelStats(
                attempts=int(row.get("attempts") or 0),
                successes=int(row.get("successes") or 0),
                captchas=int(row.get("captchas") or 0),
                blocks=int(row.get("blocks") or 0),
            )

    def _persist(self) -> None:
        if self._store is None:
            return
        rows = [
            {
                "platform": platform.value,
                "channel": channel.value,
                "attempts": stats.attempts,
                "successes": stats.successes,
                "captchas": stats.captchas,
                "blocks": stats.blocks,
            }
            for (platform, channel), stats in self._stats.items()
        ]
        self._store.save(STATE_FILE, {"stats": rows})

    def record(self, platform: Platform, channel: ChannelKind, grade: str) -> None:
        key = (platform, channel)
        stats = self._stats.setdefault(key, ChannelStats())
        stats.attempts += 1
        if grade in ("ok", "partial"):
            stats.successes += 1
        elif grade == "captcha":
            stats.captchas += 1
        elif grade == "blocked":
            stats.blocks += 1
        self._persist()

    def stats_for(self, platform: Platform, channel: ChannelKind) -> ChannelStats:
        return self._stats.get((platform, channel), ChannelStats())

    def select_channel(
        self,
        task: CollectTask,
        *,
        ensan_available: bool,
        playwright_available: bool,
        handaas_available: bool,
    ) -> ChannelKind:
        if task.force_channel:
            return task.force_channel

        if task.platform == Platform.HANDAAS:
            if handaas_available:
                return ChannelKind.HANDAAS_API
            raise RuntimeError("Handaas channel unavailable; set integrations.handaas credentials")

        if task.platform in _REGISTRY_PLATFORMS:
            if self._config.ensan_only:
                if not ensan_available:
                    raise RuntimeError(
                        "ENScan_GO unavailable; start enscan -api on :31000 "
                        "(ensan_only=true, no playwright scrape fallback)"
                    )
                return ChannelKind.ENSCAN_GO

            # Legacy path (ensan_only=false): optional interactive scrape
            force_pw = set(self._config.force_playwright_for)
            if force_pw.intersection(task.fields) and playwright_available:
                return ChannelKind.PLAYWRIGHT
            ensan_stats = self.stats_for(task.platform, ChannelKind.ENSCAN_GO)
            if ensan_available and ensan_stats.success_rate >= self._config.min_success_rate_for_enscan:
                return ChannelKind.ENSCAN_GO
            if playwright_available:
                return ChannelKind.PLAYWRIGHT
            if ensan_available:
                return ChannelKind.ENSCAN_GO

        if ensan_available:
            return ChannelKind.ENSCAN_GO
        if playwright_available:
            return ChannelKind.PLAYWRIGHT

        raise RuntimeError("No collection channel available; enable ensan_go in config")
