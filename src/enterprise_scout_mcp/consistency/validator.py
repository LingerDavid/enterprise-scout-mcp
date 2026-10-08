"""Environment consistency — persona features must align before egress."""

from __future__ import annotations

import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from enterprise_scout_mcp.models import PersonaProfile


@dataclass(frozen=True)
class ConsistencyReport:
    ok: bool
    violations: tuple[str, ...] = ()


_OS_UA_HINTS: dict[str, tuple[str, ...]] = {
    "windows": ("windows nt", "win64", "wow64"),
    "macos": ("macintosh", "mac os x"),
    "linux": ("linux", "x11"),
    "android": ("android",),
    "ios": ("iphone", "ipad", "ipod"),
}


_IANA_TZ_RE = re.compile(r"^[A-Za-z_]+(?:/[A-Za-z0-9_\-+]+)+$|^UTC$|^GMT$")


def _looks_like_iana_tz(name: str) -> bool:
    return bool(_IANA_TZ_RE.match((name or "").strip()))


def _normalize_os(raw: str) -> str:
    key = (raw or "").strip().lower().replace(" ", "")
    aliases = {
        "win": "windows",
        "win32": "windows",
        "win64": "windows",
        "mac": "macos",
        "osx": "macos",
        "darwin": "macos",
    }
    return aliases.get(key, key)


class EnvironmentValidator:
    """Checks TLS/UA/locale/geo/timezone/OS binding vs persona (architecture §一致性校验)."""

    def validate(
        self,
        persona: PersonaProfile,
        *,
        outbound_headers: dict[str, str] | None = None,
        proxy_country: str | None = None,
        tls_profile: str | None = None,
        host_timezone: str | None = None,
        host_os: str | None = None,
    ) -> ConsistencyReport:
        violations: list[str] = []
        headers = {k.lower(): v for k, v in (outbound_headers or {}).items()}

        expected_ua = persona.user_agent
        if expected_ua and headers.get("user-agent") and headers["user-agent"] != expected_ua:
            violations.append("user-agent mismatch vs persona")

        if proxy_country and persona.network.get("country") and proxy_country != persona.network["country"]:
            violations.append("proxy geo mismatch vs persona.network.country")

        expected_tls = persona.network.get("tls_impersonate")
        if expected_tls and tls_profile and expected_tls != tls_profile:
            violations.append("TLS impersonation profile mismatch")

        expected_locale = persona.locale
        accept_lang = headers.get("accept-language", "")
        if expected_locale and accept_lang and expected_locale.split("-")[0] not in accept_lang:
            violations.append("accept-language mismatch vs persona locale")

        # Language vs system locale (device.locale vs Accept-Language primary tag)
        device_lang = str(persona.device.get("language") or expected_locale or "").split("-")[0]
        if device_lang and accept_lang:
            primary = accept_lang.split(",")[0].strip().split("-")[0].lower()
            if primary and device_lang.lower() != primary:
                violations.append("language mismatch vs persona device.language")

        # Timezone: IANA-shaped name; resolve when tzdb available (needs tzdata on Windows)
        tz_name = persona.timezone
        if tz_name:
            if not _looks_like_iana_tz(tz_name):
                violations.append(f"invalid persona timezone: {tz_name}")
            else:
                try:
                    ZoneInfo(tz_name)
                except ZoneInfoNotFoundError:
                    # Host missing tzdb (e.g. Windows without tzdata) — skip resolve
                    pass
                except Exception:  # noqa: BLE001 — ZoneInfo platform gaps
                    pass
            if host_timezone and host_timezone != tz_name:
                violations.append("host timezone mismatch vs persona.device.timezone")

        # OS vs User-Agent / persona.device.os
        persona_os = _normalize_os(str(persona.device.get("os") or ""))
        ua_lower = (expected_ua or headers.get("user-agent") or "").lower()
        if persona_os and ua_lower:
            hints = _OS_UA_HINTS.get(persona_os)
            if hints and not any(h in ua_lower for h in hints):
                violations.append("user-agent OS hint mismatch vs persona.device.os")
        if host_os and persona_os:
            if _normalize_os(host_os) != persona_os:
                violations.append("host OS mismatch vs persona.device.os")

        # Sec-CH-UA platform hint when present
        sec_platform = headers.get("sec-ch-ua-platform", "").strip('"').lower()
        if sec_platform and persona_os:
            if persona_os == "windows" and "windows" not in sec_platform:
                violations.append("sec-ch-ua-platform mismatch vs persona.device.os")
            if persona_os == "macos" and "mac" not in sec_platform:
                violations.append("sec-ch-ua-platform mismatch vs persona.device.os")

        return ConsistencyReport(ok=not violations, violations=tuple(violations))


def ua_implies_os(user_agent: str) -> str | None:
    """Best-effort OS guess from UA — used by doctor / tests."""
    lower = user_agent.lower()
    for os_name, hints in _OS_UA_HINTS.items():
        if any(h in lower for h in hints):
            return os_name
    return None
