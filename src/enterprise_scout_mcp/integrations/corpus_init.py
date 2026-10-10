"""Initialize EnterpriseLake corpus directories with samples."""

from __future__ import annotations

import json
from pathlib import Path

_L3_SAMPLE = {
    "keyword": "示例企业",
    "payload": {"title": "Example academic record", "source": "corpus-init"},
}
_JUDICIAL_SAMPLE = {
    "keyword": "示例企业",
    "payload": {"cases": [], "note": "Replace with real judicial corpus rows"},
}


def init_corpus_dirs(
    l3_dir: Path,
    judicial_dir: Path,
    *,
    write_samples: bool = True,
) -> dict:
    created: list[str] = []
    for path in (l3_dir, judicial_dir):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(str(path))
    samples: dict[str, str] = {}
    if write_samples:
        l3_sample = l3_dir / "_example.jsonl"
        if not l3_sample.exists():
            l3_sample.write_text(
                json.dumps(_L3_SAMPLE, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            samples["l3"] = str(l3_sample)
        jud_sample = judicial_dir / "_example.jsonl"
        if not jud_sample.exists():
            jud_sample.write_text(
                json.dumps(_JUDICIAL_SAMPLE, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            samples["judicial"] = str(jud_sample)
    readme = l3_dir.parent / "README.txt"
    if not readme.exists():
        readme.write_text(
            "Drop JSON/JSONL under l3/ and judicial/. See enterprise-scout-mcp/docs/corpus-schema.md\n",
            encoding="utf-8",
        )
    return {"created": created, "samples": samples, "readme": str(readme)}
