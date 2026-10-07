"""ENScan_GO HTTP API adapter — fast batch channel."""

from __future__ import annotations

from typing import Any

import httpx

from enterprise_scout_mcp.config import EnsanGoConfig
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    PersonaProfile,
    Platform,
    ResultGrade,
)
from enterprise_scout_mcp.channels.base import CollectionChannel
from enterprise_scout_mcp.transport.egress import EgressContext

_PLATFORM_TYPE = {
    Platform.AIQICHA: "aqc",
    Platform.TIANYANCHA: "tyc",
    Platform.KUAICHA: "kc",
    Platform.RISKBIRD: "rb",
}


class EnsanGoChannel(CollectionChannel):
    kind = ChannelKind.ENSCAN_GO.value

    def __init__(self, config: EnsanGoConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def available(self) -> bool:
        if not self._config.enabled:
            return False
        try:
            r = self._client.get("/")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def collect(
        self,
        task: CollectTask,
        persona: PersonaProfile,
        *,
        egress: EgressContext | None = None,
    ) -> CollectResult:
        _ = egress
        scan_type = _PLATFORM_TYPE.get(task.platform, self._config.default_type)
        params: dict[str, Any] = {
            "name": task.keyword,
            "type": scan_type,
            "depth": task.depth,
        }
        if task.fields:
            params["filed"] = ",".join(task.fields)

        try:
            r = self._client.get("/api/info", params=params)
            payload = r.json()
        except httpx.HTTPError as exc:
            return CollectResult(
                task=task,
                channel=ChannelKind.ENSCAN_GO,
                grade=ResultGrade.ERROR,
                message=str(exc),
                persona_id=persona.id,
            )

        code = payload.get("code", r.status_code)
        message = str(payload.get("message", ""))
        data = payload.get("data") or {}

        grade = ResultGrade.OK
        lower = message.lower()
        if "\u9a8c\u8bc1\u7801" in message or "captcha" in lower:
            grade = ResultGrade.CAPTCHA
        elif code != 200 or not data:
            grade = ResultGrade.PARTIAL if data else ResultGrade.ERROR

        return CollectResult(
            task=task,
            channel=ChannelKind.ENSCAN_GO,
            grade=grade,
            data=data if isinstance(data, dict) else {"raw": data},
            message=message,
            persona_id=persona.id,
        )
