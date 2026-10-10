"""Fine UI HTTP BFF."""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("fastapi") is None,
    reason="fastapi not installed (pip install -e '.[ui]')",
)


def test_health_and_warehouse() -> None:
    from fastapi.testclient import TestClient

    from enterprise_scout_mcp.http.app import create_app

    client = TestClient(create_app())
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True

    wh = client.get("/api/warehouse")
    assert wh.status_code == 200
    body = wh.json()
    assert "counts" in body or body.get("dry_run_ok") is False


def test_verify_endpoint() -> None:
    from fastapi.testclient import TestClient

    from enterprise_scout_mcp.http.app import create_app

    client = TestClient(create_app())
    resp = client.get("/api/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert "checks" in data
    assert data["checks"]["fine_ui"] is True
