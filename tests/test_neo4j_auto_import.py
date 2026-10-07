"""neo4j.auto_import wiring on scheduler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from enterprise_scout_mcp.config import AppConfig, Neo4jConfig
from enterprise_scout_mcp.models import ChannelKind, CollectResult, CollectTask, Platform, ResultGrade
from enterprise_scout_mcp.scheduler import CollectorScheduler


def test_maybe_import_skipped_when_disabled() -> None:
    config = AppConfig(neo4j=Neo4jConfig(enabled=False, auto_import=True))
    scheduler = CollectorScheduler(config)
    try:
        assert scheduler.maybe_import_neo4j() is None
    finally:
        scheduler.close()


def test_maybe_import_calls_loader_when_enabled() -> None:
    config = AppConfig(neo4j=Neo4jConfig(enabled=True, auto_import=True))
    scheduler = CollectorScheduler(config)
    try:
        with patch(
            "enterprise_scout_mcp.warehouse.neo4j_loader.import_warehouse"
        ) as mock_import:
            mock_stats = MagicMock()
            mock_stats.to_dict.return_value = {"entities_merged": 2}
            mock_import.return_value = mock_stats
            out = scheduler.maybe_import_neo4j()
        assert out == {"ok": True, "entities_merged": 2}
        mock_import.assert_called_once()
    finally:
        scheduler.close()


def test_run_passes_import_flag() -> None:
    config = AppConfig()
    scheduler = CollectorScheduler(config)
    try:
        with patch.object(scheduler._channels[ChannelKind.ENSCAN_GO], "available", return_value=True), \
             patch.object(scheduler._channels[ChannelKind.ENSCAN_GO], "collect") as mock_collect, \
             patch.object(scheduler, "maybe_import_neo4j") as mock_neo:
            mock_collect.return_value = CollectResult(
                task=CollectTask(keyword="X", platform=Platform.AIQICHA),
                channel=ChannelKind.ENSCAN_GO,
                grade=ResultGrade.OK,
                data={},
            )
            with patch.object(scheduler._output, "persist"):
                with patch.object(scheduler._behavior, "wait_before_request"):
                    with patch.object(scheduler._behavior, "can_proceed", return_value=(True, "")):
                        scheduler.run(
                            CollectTask(keyword="X", platform=Platform.AIQICHA),
                            import_neo4j=False,
                        )
            mock_neo.assert_not_called()
    finally:
        scheduler.close()
