"""Corpus warehouse supplements and init."""

from __future__ import annotations

import json

from enterprise_scout_mcp.integrations.corpus_init import init_corpus_dirs
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    Dimension,
    Platform,
    ResultGrade,
    SourceTier,
)
from enterprise_scout_mcp.output.corpus_schema import supplement_row
from enterprise_scout_mcp.output.corpus_writer import append_corpus_supplement
from enterprise_scout_mcp.output.entity_schema import entity_row


def test_supplement_row_l3() -> None:
    task = CollectTask(keyword="Acme", platform=Platform.GSXT, dimensions=(Dimension.REGISTRY,))
    result = CollectResult(
        task=task,
        channel=ChannelKind.ACADEMIC_L3,
        grade=ResultGrade.OK,
        data={
            "academic": {"title": "paper"},
            "corpus": {"source_file": "papers.jsonl"},
        },
        source_tier=SourceTier.L3,
        dimension=Dimension.REGISTRY,
    )
    row = supplement_row(result)
    assert row is not None
    assert row["corpus_file"] == "papers.jsonl"
    assert json.loads(row["payload_json"])["title"] == "paper"


def test_append_corpus_supplement_parquet(tmp_path) -> None:
    task = CollectTask(keyword="Acme", platform=Platform.GSXT, dimensions=(Dimension.JUDICIAL,))
    result = CollectResult(
        task=task,
        channel=ChannelKind.DEFERRED,
        grade=ResultGrade.OK,
        data={"judicial": {"cases": [{"id": "J1"}]}, "corpus": {"source_file": "c.jsonl"}},
        dimension=Dimension.JUDICIAL,
    )
    path = append_corpus_supplement(result, tmp_path)
    assert path is not None
    assert path.name == "part.parquet"
    assert "judicial" in str(path)


def test_entity_row_corpus_academic() -> None:
    task = CollectTask(keyword="Acme Lab", platform=Platform.GSXT)
    result = CollectResult(
        task=task,
        channel=ChannelKind.ACADEMIC_L3,
        grade=ResultGrade.OK,
        data={"academic": {"name": "Acme Lab", "credit_code": "91320507MA1YW0G9XC"}},
        source_tier=SourceTier.L3,
        dimension=Dimension.REGISTRY,
    )
    row = entity_row(result)
    assert row["name"] == "Acme Lab"
    assert row["credit_code"] == "91320507MA1YW0G9XC"
    assert row["source_tier"] == "l3"


def test_init_corpus_dirs(tmp_path) -> None:
    l3 = tmp_path / "l3"
    jud = tmp_path / "judicial"
    listed = tmp_path / "listed"
    report = init_corpus_dirs(l3, jud, listed, write_samples=True)
    assert l3.is_dir()
    assert jud.is_dir()
    assert listed.is_dir()
    assert (l3 / "_example.jsonl").is_file()
    assert (jud / "_example.jsonl").is_file()
    assert (listed / "_example.jsonl").is_file()
    assert "l3" in report["samples"]
    assert "listed" in report["samples"]
