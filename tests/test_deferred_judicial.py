"""Judicial dimension via local corpus."""

from __future__ import annotations

import json

from enterprise_scout_mcp.channels.deferred import DeferredDimensionChannel
from enterprise_scout_mcp.config import CorpusConfig
from enterprise_scout_mcp.models import CollectTask, Dimension, PersonaProfile, Platform, ResultGrade


def test_judicial_corpus_hit(tmp_path) -> None:
    corpus = tmp_path / "judicial"
    corpus.mkdir()
    (corpus / "cases.jsonl").write_text(
        json.dumps(
            {"keyword": "Acme", "payload": {"cases": [{"id": "J1"}]}},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    channel = DeferredDimensionChannel(
        CorpusConfig(judicial_dir=str(corpus)),
        project_root=tmp_path,
    )
    result = channel.collect(
        CollectTask(keyword="Acme", platform=Platform.GSXT, dimensions=(Dimension.JUDICIAL,)),
        PersonaProfile(id="t", device={}, network={}, behavior={}),
    )
    assert result.grade == ResultGrade.OK
    assert result.data["judicial"]["cases"][0]["id"] == "J1"
