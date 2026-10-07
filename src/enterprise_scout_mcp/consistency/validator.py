"""Environment consistency 鈥?persona features must align before egress."""

from __future__ import annotations

from dataclasses import dataclass

from enterprise_scout_mcp.models import PersonaProfile


@dataclass(frozen=True)
class ConsistencyReport:
    ok: bool
    violations: tuple[str, ...] = ()


class EnvironmentValidator:
    def validate(
        self,
        persona: PersonaProfile,
        *,
        outbound_headers: dict[str, str] | None = None,
        proxy_country: str | None = None,
        tls_profile: str | None = None,
    ) -> ConsistencyReport:
        violations: list[str] = []
        headers = {k.lower(): v for k, v in (outbound_headers or {}).items()}

        expected_ua = persona.user_agent
        if expected_ua and headers.get("user-agent") and headers["user-agent"] != expected_ua:
            violations.append("user-agent mismatch vs persona")

        expected_tz = persona.timezone
        if proxy_country and persona.network.get("country") and proxy_country != persona.network["country"]:
            violations.append("proxy geo mismatch vs persona.network.country")

        expected_tls = persona.network.get("tls_impersonate")
        if expected_tls and tls_profile and expected_tls != tls_profile:
            violations.append("TLS impersonation profile mismatch")

        expected_locale = persona.locale
        accept_lang = headers.get("accept-language", "")
        if expected_locale and accept_lang and expected_locale.split("-")[0] not in accept_lang:
            violations.append("accept-language mismatch vs persona locale")

        return ConsistencyReport(ok=not violations, violations=tuple(violations))
