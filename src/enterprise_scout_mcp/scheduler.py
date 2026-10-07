"""Core orchestrator — persona → route → behavior → consistency → channel → output."""

from __future__ import annotations

from pathlib import Path

from enterprise_scout_mcp.behavior.orchestrator import BehaviorOrchestrator
from enterprise_scout_mcp.captcha.handler import CaptchaHandler, CaptchaStrategy
from enterprise_scout_mcp.channels.base import CollectionChannel
from enterprise_scout_mcp.channels.ensan_go import EnsanGoChannel
from enterprise_scout_mcp.channels.handaas_api import HandaasChannel
from enterprise_scout_mcp.channels.playwright_aiqicha import PlaywrightAiqichaChannel
from enterprise_scout_mcp.config import AppConfig, resolve_project_root
from enterprise_scout_mcp.consistency.validator import EnvironmentValidator
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    ResultGrade,
)
from enterprise_scout_mcp.output.router import OutputRouter
from enterprise_scout_mcp.persona.engine import PersonaEngine
from enterprise_scout_mcp.routing.risk_router import RiskAwareRouter
from enterprise_scout_mcp.state.store import StateStore
from enterprise_scout_mcp.transport.curl_cffi_backend import CurlCffiTransport
from enterprise_scout_mcp.transport.egress import EgressContext
from enterprise_scout_mcp.transport.proxy_pool import ProxyPoolClient


class CollectorScheduler:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        root = resolve_project_root()
        state_dir = Path(config.state_dir)
        if not state_dir.is_absolute():
            state_dir = root / state_dir
        self._store = StateStore(state_dir) if config.state_persist else None

        self._persona = PersonaEngine(config.personas.dir)
        self._router = RiskAwareRouter(config.routing, store=self._store)
        self._behavior = BehaviorOrchestrator(config.behavior, store=self._store)
        self._consistency = EnvironmentValidator()
        self._output = OutputRouter(config.output)
        self._proxy = self._build_proxy_client()
        self._captcha = CaptchaHandler(
            proxy_client=self._proxy,
            default_strategy=CaptchaStrategy.ROTATE_IP,
        )

        self._channels: dict[ChannelKind, CollectionChannel] = {
            ChannelKind.ENSCAN_GO: EnsanGoChannel(config.integrations.ensan_go),
            ChannelKind.PLAYWRIGHT: PlaywrightAiqichaChannel(
                config.integrations.playwright,
                project_root=root,
            ),
            ChannelKind.HANDAAS_API: HandaasChannel(config.integrations.handaas),
        }
        self._transport = (
            CurlCffiTransport(config.integrations.curl_cffi.impersonate)
            if config.integrations.curl_cffi.enabled
            else None
        )

    def _build_proxy_client(self) -> ProxyPoolClient | None:
        pp = self._config.integrations.proxy_pool
        if not pp.enabled:
            return None
        return ProxyPoolClient(pp.base_url)

    def close(self) -> None:
        for channel in self._channels.values():
            close = getattr(channel, "close", None)
            if callable(close):
                close()
        if self._proxy is not None:
            self._proxy.close()

    def _build_egress(self, persona, proxy_url: str | None) -> EgressContext:
        curl = self._config.integrations.curl_cffi
        headers = self._transport.build_headers(persona) if self._transport else {}
        return EgressContext(
            proxy_url=proxy_url,
            impersonate=curl.impersonate if curl.enabled else None,
            user_agent=headers.get("User-Agent") or persona.user_agent or None,
            accept_language=headers.get("Accept-Language") or persona.locale or None,
        )

    def run(self, task: CollectTask, *, persona_id: str | None = None) -> CollectResult:
        pid = persona_id or self._config.personas.default
        persona = self._persona.load(pid)

        allowed, reason = self._behavior.can_proceed(pid)
        if not allowed:
            return CollectResult(
                task=task,
                channel=ChannelKind.ENSCAN_GO,
                grade=ResultGrade.BLOCKED,
                message=reason,
                persona_id=pid,
            )

        channel_kind = self._router.select_channel(
            task,
            ensan_available=self._channels[ChannelKind.ENSCAN_GO].available(),
            playwright_available=self._channels[ChannelKind.PLAYWRIGHT].available(),
            handaas_available=self._channels[ChannelKind.HANDAAS_API].available(),
        )
        channel = self._channels[channel_kind]

        proxy_url: str | None = None
        if self._proxy:
            endpoint = self._proxy.get(https=True)
            if endpoint:
                proxy_url = endpoint.url

        headers: dict[str, str] = {}
        if self._transport:
            headers = self._transport.build_headers(persona)

        report = self._consistency.validate(
            persona,
            outbound_headers=headers,
            proxy_country=persona.network.get("country"),
            tls_profile=self._config.integrations.curl_cffi.impersonate,
        )
        if not report.ok:
            return CollectResult(
                task=task,
                channel=channel_kind,
                grade=ResultGrade.ERROR,
                message="; ".join(report.violations),
                persona_id=pid,
            )

        egress = self._build_egress(persona, proxy_url)
        self._behavior.wait_before_request(pid)
        result = channel.collect(task, persona, egress=egress)
        result.persona_id = pid

        self._router.record(task.platform, channel_kind, result.grade.value)

        if result.grade in (ResultGrade.OK, ResultGrade.PARTIAL):
            self._behavior.on_success(pid)
        elif result.grade == ResultGrade.CAPTCHA:
            self._behavior.on_captcha(pid)
            action = self._captcha.handle(result, bad_proxy=proxy_url)
            if action.retry:
                return self.run(task, persona_id=pid)
        elif result.grade == ResultGrade.BLOCKED:
            self._behavior.on_block(pid)

        self._output.persist(result)
        return result
