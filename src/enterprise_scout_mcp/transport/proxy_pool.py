"""proxy_pool HTTP client 鈥?GET /get, /pop, /delete."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ProxyEndpoint:
    host: str
    port: int
    https: bool = False

    @property
    def url(self) -> str:
        scheme = "https" if self.https else "http"
        return f"{scheme}://{self.host}:{self.port}"


class ProxyPoolClient:
    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _parse(data: dict, *, https: bool) -> ProxyEndpoint | None:
        if not data or data.get("code") == 0:
            return None
        raw = str(data.get("proxy", ""))
        if not raw or ":" not in raw:
            return None
        host, _, port_str = raw.partition(":")
        return ProxyEndpoint(
            host=host,
            port=int(port_str),
            https=bool(data.get("https", https)),
        )

    def get(self, *, https: bool = False) -> ProxyEndpoint | None:
        r = self._client.get(f"{self._base}/get/", params={"type": "https" if https else ""})
        r.raise_for_status()
        return self._parse(r.json(), https=https)

    def pop(self, *, https: bool = False) -> ProxyEndpoint | None:
        r = self._client.get(f"{self._base}/pop/", params={"type": "https" if https else ""})
        r.raise_for_status()
        return self._parse(r.json(), https=https)

    def delete(self, proxy: str) -> None:
        self._client.get(f"{self._base}/delete/", params={"proxy": proxy}).raise_for_status()
