# enterprise-scout-mcp

MCP-first enterprise registry intelligence orchestrator.

## Boundaries

- Output lands in EnterpriseLake `G:/enterprise_lake/` (not TickFlow `tyc_warehouse`).
- Does not touch tradecraft Gate / armed / OMS.
- Complements `enterprise-mcp-server` (Handaas single API); registry scrape goes **ENScan only** (`routing.ensan_only`, no Playwright page fallback).

## Entry points

| Command | Purpose |
|---------|---------|
| `enterprise-scout-mcp` | MCP server (stdio, default) |
| `enterprise-scout-mcp streamable-http` | MCP over HTTP |
| `escout` | Dev CLI (collect L1/L2, sync-gsxt-session, smoke-registry-l1, drain-retry) |

## Verify

```powershell
cd E:\Project\enterprise-scout-mcp
.\.venv\Scripts\pytest -q
.\.venv\Scripts\escout doctor
```
