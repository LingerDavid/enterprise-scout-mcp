"""Load config.yaml with sane defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class EnsanGoConfig(BaseModel):
    enabled: bool = True
    base_url: str = "http://127.0.0.1:31000"
    default_type: str = "aqc"
    timeout_seconds: int = 120
    config_path: str = "../ENScan_GO/config.yaml"


class ProxyPoolConfig(BaseModel):
    enabled: bool = False
    base_url: str = "http://127.0.0.1:5010"


class HandaasConfig(BaseModel):
    enabled: bool = False
    integrator_id: str = ""
    secret_id: str = ""
    secret_key: str = ""


class PlaywrightConfig(BaseModel):
    enabled: bool = False
    headless: bool = True
    cookie_file: str = "./secrets/aiqicha_cookies.txt"
    aiqicha_scraper_dir: str = "../aiqicha_scraper"
    companies_db: str = "../aiqicha_scraper/companies.db"


class CurlCffiConfig(BaseModel):
    enabled: bool = True
    impersonate: str = "chrome131"


class IntegrationsConfig(BaseModel):
    ensan_go: EnsanGoConfig = Field(default_factory=EnsanGoConfig)
    proxy_pool: ProxyPoolConfig = Field(default_factory=ProxyPoolConfig)
    handaas: HandaasConfig = Field(default_factory=HandaasConfig)
    playwright: PlaywrightConfig = Field(default_factory=PlaywrightConfig)
    curl_cffi: CurlCffiConfig = Field(default_factory=CurlCffiConfig)


class PersonasConfig(BaseModel):
    dir: str = "./personas"
    default: str = "desktop_chrome_cn"


class BehaviorConfig(BaseModel):
    global_daily_quota: int = 5000
    persona_daily_quota: int = 200
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 8.0
    cooldown_after_captcha_seconds: int = 600
    cooldown_after_block_seconds: int = 1800


class RoutingConfig(BaseModel):
    min_success_rate_for_enscan: float = 0.6
    prefer_enscan_for: list[str] = Field(
        default_factory=lambda: ["icp", "app", "wechat", "invest", "branch"]
    )
    force_playwright_for: list[str] = Field(
        default_factory=lambda: ["js_challenge", "login_required", "captcha"]
    )


class OutputConfig(BaseModel):
    warehouse_dir: str = "G:/enterprise_lake/warehouse"
    raw_dir: str = "G:/enterprise_lake/raw"
    parquet_enabled: bool = True
    grade_routes: dict[str, str] = Field(
        default_factory=lambda: {
            "ok": "warehouse",
            "partial": "raw",
            "captcha": "retry_queue",
            "blocked": "dead_letter",
        }
    )


class AppConfig(BaseModel):
    data_root: str = "G:/enterprise_lake"
    personas: PersonasConfig = Field(default_factory=PersonasConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def load_config(path: str | Path | None = None) -> AppConfig:
    candidates = [
        Path(path) if path else None,
        Path("config.yaml"),
        Path(__file__).resolve().parents[2] / "config.yaml",
    ]
    raw: dict[str, Any] = {}
    for candidate in candidates:
        if candidate and candidate.is_file():
            raw = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            break
    return AppConfig.model_validate(raw)
