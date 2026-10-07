"""Risk-aware routing — pick channel from platform stats + task shape."""

from __future__ import annotations

from enterprise_scout_mcp.config import RoutingConfig
from enterprise_scout_mcp.models import (
    ChannelKind,
    ChannelStats,
    CollectTask,
    Platform,
)


class RiskAwareRouter:
    def __init__(self, config: RoutingConfig) -> None:
        self._config = config
        self._stats: dict[tuple[Platform, ChannelKind], ChannelStats] = {}

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

        # Explicit platform → ENScan mapping (mirrors ENScan_GO -type flag)
        if task.platform in (Platform.AIQICHA, Platform.TIANYANCHA, Platform.KUAICHA, Platform.RISKBIRD):
            ensan_stats = self.stats_for(task.platform, ChannelKind.ENSCAN_GO)
            if ensan_available and ensan_stats.success_rate >= self._config.min_success_rate_for_enscan:
                bulk_fields = set(self._config.prefer_enscan_for)
                if not task.fields or bulk_fields.intersection(task.fields):
                    return ChannelKind.ENSCAN_GO

        if task.platform == Platform.HANDAAS and handaas_available:
            return ChannelKind.HANDAAS_API

        if playwright_available:
            return ChannelKind.PLAYWRIGHT

        if ensan_available:
            return ChannelKind.ENSCAN_GO

        raise RuntimeError("No collection channel available; enable ensan_go or playwright in config")
