# Corpus schema (L3 / judicial)

Local fallback for dimensions without live scrape channels. Files live under:

| Tier | Config key | Default path |
|------|------------|--------------|
| L3 academic | `integrations.corpus.l3_dir` | `G:/enterprise_lake/corpus/l3` |
| Judicial | `integrations.corpus.judicial_dir` | `G:/enterprise_lake/corpus/judicial` |

## File formats

Supported extensions: `*.json`, `*.jsonl`.

### JSONL (one record per line)

```json
{"keyword": "苏州挚途", "payload": {"title": "Supply chain paper", "year": 2024}}
{"name": "Acme Corp", "credit_code": "91320507MA1YW0G9XC", "payload": {"cases": []}}
```

### JSON array

```json
[
  {"keyword": "小米", "payload": {"abstract": "..."}}
]
```

### JSON wrapper

```json
{
  "records": [
    {"keyword": "小米", "payload": {"abstract": "..."}}
  ]
}
```

## Matching

Lookup scans all corpus files and returns the first row where any of these fields match the collect keyword (case-insensitive, substring allowed for names):

- `keyword`, `name`, `企业名称`, `company_name`, `matchKeyword`
- `credit_code`, `socialCreditCode`, `统一社会信用代码`, `scCode`

Nested `payload` objects are searched recursively.

## Listed filings (`corpus/listed`)

Pre-extracted annual / interim report rows for the value dossier. One JSON object per issuer filing:

```json
{
  "issuer_id": "91110000710928885H",
  "issuer_name": "示例股份有限公司",
  "security_id": "SSE:600000",
  "exchange": "SSE",
  "code": "600000",
  "period": "2024",
  "scope": "consolidated",
  "document_id": "ann-2024",
  "document_date": "2025-03-31",
  "facts": [
    {"statement": "income", "item_code": "revenue", "value": "1000000000", "label": "营业收入"}
  ],
  "segments": [
    {"kind": "product", "name": "示例产品", "revenue": "700000000", "cost": "400000000"}
  ]
}
```

`escout corpus import-listed` writes `warehouse/listed/{identity,facts,segments,holders}/part.parquet`. Files named `_example*` are skipped on import.

### Sampling live disclosure (cninfo + Eastmoney)

```powershell
escout corpus sample-listed 600519.SH --year 2024
```

- 巨潮：年报公告索引 + PDF 落到 `corpus/listed/pdf/`；`document_id` 形如 `cninfo:{announcementId}`。
- 东财公司概况：统一社会信用代码 → `issuer_id`，写入 `warehouse/listed/identity`。
- 东财 F10：十大股东写入 corpus JSONL 的 `holders`，并追加 `warehouse/listed/holders`。
- 三大表数字不在这里拉；用 tradecraft `python -m scripts.sample_listed_qmt_ingest`（QMT）；会读 identity 把 facts 挂到信用代码上。

## CLI

```powershell
escout collect 苏州挚途 --prefer-tier l3 --dims registry
escout collect 苏州挚途 --dims judicial
escout corpus init
escout corpus status
escout corpus sample-listed 600519.SH --year 2024
escout corpus import-listed --dry-run
escout corpus import-listed
```

See `escout doctor` → `corpus` for directory file counts.
