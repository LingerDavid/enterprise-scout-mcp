# enterprise-scout-mcp

[![test](https://github.com/LingerDavid/enterprise-scout-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/LingerDavid/enterprise-scout-mcp/actions/workflows/test.yml)

企业工商/穿透情报 **MCP 服务**。Python 编排层（人设、风控路由、行为配额）+ 多通道采集，输出到 [EnterpriseLake](../EnterpriseLake) `G:/enterprise_lake/`。

与 `enterprise-mcp-server`（Handaas 单源 API）互补：工商主路径只走 ENScan_GO；Handaas 为可选付费补源。

## MCP 工具

| 工具 | 说明 |
|------|------|
| `enterprise_collect` | 按关键词采集（平台 / 深度 / fields / persona） |
| `enterprise_search` | 轻量搜索（depth=0） |
| `enterprise_collect_batch` | 批量采集（支持 checkpoint） |
| `sync_enscan_cookies` | 把本地 cookie 写入 ENScan config |
| `scout_drain_retry` | 重跑 `raw/retry_queue`（成功则归档） |
| `scout_doctor` | 检查 ENScan / Handaas / 人设（可 probe sidecar） |
| `scout_sidecars` | 探活 ENScan / proxy_pool |
| `scout_import_neo4j` | warehouse parquet → Neo4j（默认 dry_run） |

## 快速启动

```powershell
cd E:\Project\enterprise-scout-mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,warehouse]"
# 浏览器回退（可选）: pip install -e ".[browser]"

copy config.example.yaml config.yaml
enterprise-scout-mcp                    # stdio（Cursor / Hermes 默认）
enterprise-scout-mcp streamable-http  # HTTP :8000
```

## Cursor / Hermes 配置

**stdio（推荐本地）：**

```json
{
  "mcpServers": {
    "enterprise-scout-mcp": {
      "command": "enterprise-scout-mcp",
      "args": [],
      "cwd": "E:/Project/enterprise-scout-mcp"
    }
  }
}
```

**streamable-http：**

```json
{
  "mcpServers": {
    "enterprise-scout-mcp": {
      "type": "streamableHttp",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## 开发 CLI

编排层调试（非 MCP 面）：

```powershell
escout doctor
escout personas
escout collect 小米 -p aiqicha
escout collect-batch --file keywords.txt -p aiqicha --checkpoint .state/batch.json
escout import-neo4j --dry-run    # 统计 warehouse 行数
escout import-neo4j              # 写入 Neo4j（需 pip install -e ".[graph]"）
escout sync-cookies --from-file ./secrets/aiqicha_cookies.txt
escout register-hermes          # 写入 ~/.hermes/config.yaml
escout doctor --probe           # 含 ENScan / proxy_pool 探活
escout smoke-sidecars           # 仅 sidecar 探活（CI/脚本用）
escout smoke-collect 小米       # 实机采集冒烟（需 ENScan 运行）
escout sync-gsxt-session --from-file cookies.json   # L1 个人登录 cookie
escout collect 苏州挚途 --dims registry --prefer-tier l1 -p gsxt
escout smoke-registry-l1 苏州挚途                  # L1 registry 穿通验收
escout drain-retry --dry-run    # 列出 retry_queue 待重跑任务
escout drain-retry --limit 20   # 重跑 captcha 队列（成功 → .archive）
```

**采集策略（三级源）：** 默认 `ensan_only` — 爱企查 / 天眼查等走 ENScan L2。L1 官方工商：`escout collect 关键词 --dims registry --prefer-tier l1 -p gsxt`（需先在 [shiming.gsxt.gov.cn](https://shiming.gsxt.gov.cn) 个人登录并 `sync-gsxt-session` 导入 cookie）。ENScan 不可用时 L2 直接报错。

默认 `fields`：`enterprise_info,partner,holds,invest,branch`（写入实体 + 股权边）。可用 `-f` / MCP `fields` 覆盖。

`state_persist: true` 时，日配额与路由成功率写入 `state_dir`（默认 `./.state/`）。`collect-batch --checkpoint` 断点续跑：仅 `ok`/`partial` 记为 done，`error`/`captcha`/`blocked` 下次会重试。

`neo4j.enabled` + `neo4j.auto_import: true` 时，单采 / 批采结束 / drain 成功后会自动 merge warehouse → Neo4j（需 `pip install -e ".[graph]"`）。

## Warehouse 输出

`output.parquet_enabled: true` 时写入 EnterpriseLake：

| 路径 | 内容 |
|------|------|
| `warehouse/entities/part.parquet` | 企业实体行 |
| `warehouse/edges/equity/part.parquet` | 股权/投资/分支边（partner/holds/invest/branch） |
| `raw/` / `raw/retry_queue/` | partial / captcha 分级 JSON |

列定义见 [docs/warehouse-schema.md](docs/warehouse-schema.md)（与 EnterpriseLake layout 对齐）。

## 架构

```
MCP (enterprise-scout-mcp)
  └─ CollectorScheduler
       ├─ TierAwareRouter     ← L1 GSXT / L2 ENScan (when --prefer-tier)
       ├─ RiskAwareRouter     ← ensan_only default for aiqicha/tyc
       ├─ GsxtOfficialChannel ← L1 registry (personal session)
       ├─ EnsanGoChannel      ← L2 ENScan :31000
       └─ HandaasChannel      ← optional paid API
```

## Sidecar

```powershell
docker compose up -d proxy_pool
# ENScan: cd ..\ENScan_GO && .\enscan.exe -api
```

## 测试

```powershell
pytest -q
```

CI: GitHub Actions workflow `.github/workflows/test.yml` runs the same suite on push/PR.
