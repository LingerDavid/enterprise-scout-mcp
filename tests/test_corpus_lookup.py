"""Corpus lookup for L3 / judicial."""

from __future__ import annotations

import json

from enterprise_scout_mcp.integrations.corpus_lookup import lookup_corpus


def test_lookup_jsonl_match(tmp_path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text(
        json.dumps({"keyword": "苏州挚途", "payload": {"title": "paper A"}}, ensure_ascii=False)
        + "\n"
        + json.dumps({"keyword": "other", "payload": {"title": "paper B"}}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    hit = lookup_corpus(tmp_path, "苏州挚途")
    assert hit is not None
    assert hit["record"]["title"] == "paper A"
    assert hit["source_file"] == "records.jsonl"


def test_lookup_miss(tmp_path) -> None:
    tmp_path.mkdir(exist_ok=True)
    assert lookup_corpus(tmp_path, "missing") is None
