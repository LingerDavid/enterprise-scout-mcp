"""Config loading."""

from __future__ import annotations

from enterprise_scout_mcp.config import AppConfig, Neo4jConfig


def test_neo4j_defaults_match_enterpriselake() -> None:
    neo = Neo4jConfig()
    assert neo.uri == "bolt://127.0.0.1:7687"
    assert neo.user == "neo4j"
    assert neo.password == "enterprise-lake-dev"
    assert neo.auto_import is False


def test_app_config_has_neo4j_section() -> None:
    cfg = AppConfig()
    assert cfg.neo4j.uri.startswith("bolt://")
