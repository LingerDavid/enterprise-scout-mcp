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
_LISTED_SAMPLE = {
    "issuer_id": "91110000710928885H",
    "issuer_name": "示例股份有限公司",
    "security_id": "SSE:600000",
    "exchange": "SSE",
    "code": "600000",
    "period": "2024",
    "scope": "consolidated",
    "document_id": "ann-example-2024",
    "document_date": "2025-03-31",
    "facts": [
        {
            "statement": "income",
            "item_code": "revenue",
            "label": "营业收入",
            "value": "1000000000",
        },
        {
            "statement": "cashflow",
            "item_code": "cfo",
            "label": "经营活动产生的现金流量净额",
            "value": "200000000",
        },
        {
            "statement": "cashflow",
            "item_code": "capex_cash",
            "label": "购建固定资产等支付的现金",
            "value": "50000000",
        },
        {
            "statement": "income",
            "item_code": "net_profit_parent",
            "label": "归属于母公司股东的净利润",
            "value": "80000000",
        },
        {
            "statement": "cashflow",
            "item_code": "cash_from_sales",
            "label": "销售商品、提供劳务收到的现金",
            "value": "1100000000",
        },
    ],
    "segments": [
        {
            "kind": "product",
            "name": "示例产品",
            "revenue": "700000000",
            "cost": "400000000",
        }
    ],
}


def init_corpus_dirs(
    l3_dir: Path,
    judicial_dir: Path,
    listed_dir: Path | None = None,
    *,
    write_samples: bool = True,
) -> dict:
    created: list[str] = []
    dirs = [l3_dir, judicial_dir]
    if listed_dir is not None:
        dirs.append(listed_dir)
    for path in dirs:
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
        if listed_dir is not None:
            listed_sample = listed_dir / "_example.jsonl"
            if not listed_sample.exists():
                listed_sample.write_text(
                    json.dumps(_LISTED_SAMPLE, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                samples["listed"] = str(listed_sample)
    readme = l3_dir.parent / "README.txt"
    if not readme.exists():
        readme.write_text(
            "Drop JSON/JSONL under l3/, judicial/, and listed/. "
            "See enterprise-scout-mcp/docs/corpus-schema.md\n",
            encoding="utf-8",
        )
    return {"created": created, "samples": samples, "readme": str(readme)}
