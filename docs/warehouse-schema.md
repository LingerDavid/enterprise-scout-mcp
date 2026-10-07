# Warehouse schema (enterprise-scout-mcp writer)

Output root: `output.warehouse_dir` (default `G:/enterprise_lake/warehouse`).

Aligns with [EnterpriseLake layout](../../EnterpriseLake/docs/layout.md). This service appends rows; downstream ETL / Neo4j import owns dedup and graph merge.

## entities/part.parquet

One row per successful or partial collect (`grade` in `ok`, `partial`).

| Column | Type | Description |
|--------|------|-------------|
| `entity_id` | string | Platform id (`pid` / `aiqicha_id` / `nameId`, …) |
| `name` | string | Canonical company name（ENScan 从 `enterprise_info[0].name` 解包） |
| `former_name` | string | Former / alias name |
| `platform` | string | `aiqicha`, `tianyancha`, `handaas`, … |
| `source_channel` | string | `enscan_go`, `playwright`, `handaas_api` |
| `query_keyword` | string | Original search keyword |
| `grade` | string | `ok` or `partial` |
| `persona_id` | string | Persona used for the request |
| `collected_at` | string | UTC ISO-8601 timestamp |
| `payload_json` | string | Full channel payload (JSON) |
| `message` | string | Orchestrator / channel message |

## edges/equity/part.parquet

Extracted from ENScan-style nested sections: `partner` / `stockholder` / `holder` (股东→`holder`), `invest` / `holds` (投资/控股→`invest`), `branch`. ENScan 统一导出键为 `name` + `scale`（见 ENSMapLN）。

| Column | Type | Description |
|--------|------|-------------|
| `src_name` | string | Source entity (holder or parent) |
| `dst_name` | string | Target entity (investee / branch) |
| `relation` | string | `invest`, `holder`, `branch` |
| `ratio` | string | Stake ratio when present |
| `section` | string | Source section key in payload |
| `platform` | string | Task platform |
| `source_channel` | string | Collect channel |
| `query_keyword` | string | Root company keyword |
| `collected_at` | string | UTC ISO-8601 |
| `payload_json` | string | Source row JSON |

## Raw JSON (graded)

| Grade | Directory |
|-------|-----------|
| `ok` | `warehouse/` (also parquet when enabled) |
| `partial` | `raw/` |
| `captcha` | `raw/retry_queue/` |
| `blocked` | `raw/dead_letter/` |

Files: `{platform}_{keyword}_{timestamp}.json`

## Neo4j import

After `docker compose up -d` in EnterpriseLake:

```powershell
pip install -e ".[graph]"
escout import-neo4j --dry-run
escout import-neo4j --uri bolt://127.0.0.1:7687 --user neo4j --password enterprise-lake-dev
```

Graph model: `(:Company {id})-[:HOLDS {percent}]->(:Company)` plus optional `[:BRANCH]`.
Penetration queries: `EnterpriseLake/cypher/equity_penetration.cypher`.
