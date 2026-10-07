"""Handaas enterprise API 鈥?same signing contract as enterprise-mcp-server."""

from __future__ import annotations

import json
from hashlib import md5

import httpx

from enterprise_scout_mcp.config import HandaasConfig
from enterprise_scout_mcp.models import (
    ChannelKind,
    CollectResult,
    CollectTask,
    PersonaProfile,
    Platform,
    ResultGrade,
)
from enterprise_scout_mcp.channels.base import CollectionChannel


class HandaasChannel(CollectionChannel):
    kind = ChannelKind.HANDAAS_API.value

    def __init__(self, config: HandaasConfig) -> None:
        self._config = config
        self._client = httpx.Client(timeout=60.0)

    def available(self) -> bool:
        return bool(
            self._config.enabled
            and self._config.integrator_id
            and self._config.secret_id
            and self._config.secret_key
        )

    def _call(self, product_id: str, params: dict) -> dict | str:
        call_params = {
            "product_id": product_id,
            "secret_id": self._config.secret_id,
            "params": json.dumps(params, ensure_ascii=False),
        }
        keys = sorted(call_params.keys())
        sign_src = "".join(str(call_params[k]) for k in keys) + self._config.secret_key
        call_params["signature"] = md5(sign_src.encode("utf-8")).hexdigest()
        url = f"https://console.handaas.com/api/v1/integrator/call_api/{self._config.integrator_id}"
        r = self._client.post(url, data=call_params)
        r.raise_for_status()
        body = r.json()
        return body.get("data") or body.get("msgCN") or body

    def collect(self, task: CollectTask, persona: PersonaProfile) -> CollectResult:
        if task.platform != Platform.HANDAAS:
            return CollectResult(
                task=task,
                channel=ChannelKind.HANDAAS_API,
                grade=ResultGrade.ERROR,
                message="Handaas channel requires platform=handaas",
                persona_id=persona.id,
            )
        try:
            data = self._call(
                "enterprise_get_enterprise_base_info",
                {"keyword": task.keyword},
            )
            grade = ResultGrade.OK if data else ResultGrade.PARTIAL
            return CollectResult(
                task=task,
                channel=ChannelKind.HANDAAS_API,
                grade=grade,
                data=data if isinstance(data, dict) else {"raw": data},
                persona_id=persona.id,
            )
        except httpx.HTTPError as exc:
            return CollectResult(
                task=task,
                channel=ChannelKind.HANDAAS_API,
                grade=ResultGrade.ERROR,
                message=str(exc),
                persona_id=persona.id,
            )
