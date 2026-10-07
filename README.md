# enterprise-scout-mcp

企业工商/穿透情报 **MCP 服务**。Python 编排层（人设、风控路由、行为配额）+ 多通道采集，输出到 [EnterpriseLake](../EnterpriseLake) `G:/enterprise_lake/`。

与 `enterprise-mcp-server`（Handaas 单源 API）互补：本服务编排 ENScan_GO / Playwright / 本地通道。

## MCP 工具

| 工具 | 说明 |
|------|------|
| `enterprise_collect` | 按关键词采集（平台、深度可配） |
| `enterprise_search` | 轻量搜索（depth=0） |
| `scout_doctor` | 检查 ENScan / Playwright / Handaas / 人设 |

## 快速启动

```powershell
cd E:\Project\enterprise-scout-mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

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
escout sync-cookies --from-file ./secrets/aiqicha_cookies.txt
escout register-hermes          # 写入 ~/.hermes/config.yaml
```

DB 未命中时，`playwright.fetch_on_miss` 会调用 `scripts/aiqicha_fetch_one.py`（httpx + cookie）抓取并 upsert 到 `companies.db`。

## 架构

```
MCP (enterprise-scout-mcp)
  └─ CollectorScheduler
       ├─ PersonaEngine
       ├─ RiskAwareRouter
       ├─ BehaviorOrchestrator
       ├─ EnvironmentValidator
       ├─ EnsanGoChannel      ← ENScan_GO :31000
       ├─ PlaywrightChannel   ← aiqicha_scraper 模式
       └─ HandaasChannel      ← enterprise-mcp-server 签名
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
