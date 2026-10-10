"""L3 academic channel with local corpus."""

from __future__ import annotations

import json

from enterprise_scout_mcp.channels.academic_l3 import AcademicL3Channel
from enterprise_scout_mcp.config import CorpusConfig
from enterprise_scout_mcp.models import (
    CollectTask,
    Dimension,
    PersonaProfile,
    Platform,
    ResultGrade,
    SourceTier,
)


def _persona() -> PersonaProfile:
    return PersonaProfile(id="t", device={}, network={}, behavior={})


def test_l3_corpus_hit(tmp_path) -> None:
    corpus = tmp_path / "l3"
    corpus.mkdir()
    (corpus / "papers.jsonl").write_text(
        json.dumps({"name": "Acme Lab", "payload": {"abstract": "x"}}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    channel = AcademicL3Channel(CorpusConfig(l3_dir=str(corpus)), project_root=tmp_path)
    assert channel.available()
    result = channel.collect(
        CollectTask(
            keyword="Acme Lab",
            platform=Platform.GSXT,
            dimensions=(Dimension.REGISTRY,),
            prefer_tier=SourceTier.L3,
        ),
        _persona(),
    )
    assert result.grade == ResultGrade.OK
    assert result.data["academic"]["abstract"] == "x"
    assert result.source_tier == SourceTier.L3
