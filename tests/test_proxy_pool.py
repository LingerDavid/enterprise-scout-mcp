"""proxy_pool response parsing."""

from __future__ import annotations

from enterprise_scout_mcp.transport.proxy_pool import ProxyPoolClient


def test_parse_proxy_success() -> None:
    ep = ProxyPoolClient._parse(  # noqa: SLF001 - unit test helper
        {"proxy": "127.0.0.1:8080", "https": True},
        https=False,
    )
    assert ep is not None
    assert ep.host == "127.0.0.1"
    assert ep.port == 8080
    assert ep.url == "https://127.0.0.1:8080"


def test_parse_empty_pool() -> None:
    ep = ProxyPoolClient._parse({"code": 0, "src": "no proxy"}, https=False)
    assert ep is None


def test_parse_missing_proxy_field() -> None:
    ep = ProxyPoolClient._parse({"https": False}, https=False)
    assert ep is None
