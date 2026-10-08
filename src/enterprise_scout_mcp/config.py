"""Load config.yaml with sane defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


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
    fetch_on_miss: bool = True
    fetch_script: str = "./scripts/aiqicha_fetch_one.py"
    nodriver_script: str = "./scripts/aiqicha_fetch_nodriver.py"
    nodriver_on_captcha: bool = True
    nodriver_user_data_dir: str = "./nodriver_data"
    fetch_timeout_seconds: float = 90.0


class CurlCffiConfig(BaseModel):
    enabled: bool = False
    impersonate: str = "chrome131"


class SessionsConfig(BaseModel):
    """Unified cookie/session store — authoritative paths for GSXT L1 and aiqicha L2."""

    dir: str = "./.state"
    gsxt: str = "gsxt_personal_session.json"
    aiqicha: str = "./secrets/aiqicha_cookies.txt"
    export_inbox: str = "./.state/session_exports"

    def gsxt_path(self, config: AppConfig | None = None) -> str:
        _ = config
        p = Path(self.gsxt)
        if p.is_absolute():
            return str(p)
        return str(Path(self.dir) / self.gsxt)

    def aiqicha_path(self, config: AppConfig | None = None) -> str:
        _ = config
        return self.aiqicha


class GsxtConfig(BaseModel):
    enabled: bool = True
    base_url: str = "https://www.gsxt.gov.cn"
    shiming_url: str = "https://shiming.gsxt.gov.cn"
    session_mode: str = "personal"  # personal | anonymous
    session_file: str = "./.state/gsxt_personal_session.json"  # wired from sessions.* on load
    search_url: str = "https://www.gsxt.gov.cn/api/search/testAi"
    search_keyword_field: str = "searchword"
    captcha_mode: str = "manual"
    browser_warmup_on_ct: bool = True  # nodriver refresh when CT 405 after JSL
    browser_warmup_wait_seconds: float = 6.0
    browser_user_data_dir: str = "./.state/gsxt_nodriver_data"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    timeout_seconds: float = 30.0


class IntegrationsConfig(BaseModel):
    gsxt: GsxtConfig = Field(default_factory=GsxtConfig)
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
    # ensan_only: L2 commercial path for aiqicha/tyc/… ; tiered: L1 GSXT when --prefer-tier l1 / -p gsxt
    source_policy: str = "ensan_only"  # ensan_only | tiered
    ensan_only: bool = True
    gsxt_allow_unavailable: bool = True  # route to GSXT even without session (returns auth_expired)
    l1_fallback_to_l2: bool = True  # tiered L1 registry fail → ENScan L2 with degraded=true
    min_success_rate_for_enscan: float = 0.0
    prefer_enscan_for: list[str] = Field(
        default_factory=lambda: ["icp", "app", "wechat", "invest", "branch", "partner", "holds"]
    )
    # Unused when ensan_only=true; kept for optional force_channel experiments.
    force_playwright_for: list[str] = Field(default_factory=list)


class OutputConfig(BaseModel):
    warehouse_dir: str = "G:/enterprise_lake/warehouse"
    raw_dir: str = "G:/enterprise_lake/raw"
    parquet_enabled: bool = True
    grade_routes: dict[str, str] = Field(
        default_factory=lambda: {
            "ok": "warehouse",
            "partial": "raw",
            "captcha": "retry_queue",
            "auth_expired": "retry_queue",
            "blocked": "dead_letter",
        }
    )


class Neo4jConfig(BaseModel):
    enabled: bool = False
    # When true, merge warehouse parquet into Neo4j after ok/partial collect
    # (and once at end of collect-batch). Requires pip install -e ".[graph]".
    auto_import: bool = False
    uri: str = "bolt://127.0.0.1:7687"
    user: str = "neo4j"
    password: str = "enterprise-lake-dev"


class AppConfig(BaseModel):
    data_root: str = "G:/enterprise_lake"
    state_dir: str = "./.state"
    state_persist: bool = True
    sessions: SessionsConfig = Field(default_factory=SessionsConfig)
    personas: PersonasConfig = Field(default_factory=PersonasConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)

    @model_validator(mode="after")
    def _wire_session_paths(self) -> AppConfig:
        """Keep integrations.* paths aligned with sessions.* (single source of truth)."""
        self.integrations.gsxt.session_file = self.sessions.gsxt_path(self)
        self.integrations.playwright.cookie_file = self.sessions.aiqicha_path(self)
        return self


def _config_candidates(path: str | Path | None) -> list[Path]:
    return [
        p
        for p in (
            Path(path) if path else None,
            Path("config.yaml"),
            Path(__file__).resolve().parents[2] / "config.yaml",
        )
        if p is not None
    ]


def resolve_project_root(path: str | Path | None = None) -> Path:
    """Directory containing config.yaml, else cwd."""
    for candidate in _config_candidates(path):
        if candidate.is_file():
            return candidate.parent
    return Path.cwd()


def load_config(path: str | Path | None = None) -> AppConfig:
    raw: dict[str, Any] = {}
    for candidate in _config_candidates(path):
        if candidate.is_file():
            raw = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            break
    return AppConfig.model_validate(raw)
