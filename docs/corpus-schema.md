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

## CLI

```powershell
escout collect 苏州挚途 --prefer-tier l3 --dims registry
escout collect 苏州挚途 --dims judicial
escout corpus init
escout corpus status
```

See `escout doctor` → `corpus` for directory file counts.
