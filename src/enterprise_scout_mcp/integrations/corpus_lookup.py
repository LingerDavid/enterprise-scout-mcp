"""Local corpus lookup for L3 academic / judicial dimensions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

_NAME_KEYS = ("keyword", "name", "企业名称", "company_name", "matchKeyword")
_CODE_KEYS = ("credit_code", "socialCreditCode", "统一社会信用代码", "scCode")


def _normalize(text: str) -> str:
    return (text or "").strip().casefold()


def _row_matches(row: dict[str, Any], keyword: str) -> bool:
    needle = _normalize(keyword)
    if not needle:
        return False
    for key in _NAME_KEYS:
        val = row.get(key)
        if val and _normalize(str(val)) == needle:
            return True
        if val and needle in _normalize(str(val)):
            return True
    for key in _CODE_KEYS:
        val = row.get(key)
        if val and _normalize(str(val)) == needle:
            return True
    payload = row.get("payload")
    if isinstance(payload, dict):
        return _row_matches(payload, keyword)
    return False


def _iter_records(path: Path) -> Iterator[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                yield row
    elif isinstance(data, dict):
        rows = data.get("records") or data.get("items")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    yield row
        else:
            yield data


def corpus_dir_stats(corpus_dir: Path) -> dict[str, Any]:
    if not corpus_dir.is_dir():
        return {"exists": False, "files": 0, "path": str(corpus_dir)}
    files = list(corpus_dir.glob("*.json")) + list(corpus_dir.glob("*.jsonl"))
    return {"exists": True, "files": len(files), "path": str(corpus_dir)}


def lookup_corpus(corpus_dir: Path, keyword: str) -> dict[str, Any] | None:
    """Return first matching record from *.json / *.jsonl under corpus_dir."""
    if not corpus_dir.is_dir():
        return None
    paths = sorted(corpus_dir.glob("*.json")) + sorted(corpus_dir.glob("*.jsonl"))
    for path in paths:
        for row in _iter_records(path):
            if _row_matches(row, keyword):
                payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
                return {
                    "source_file": path.name,
                    "matched_keyword": keyword,
                    "record": payload if isinstance(payload, dict) else {"raw": payload},
                }
    return None
