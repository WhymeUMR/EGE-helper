"""Block 12: /health, /live, /ready, /metrics, /api/v1/meta/*"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_health(api_client):
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_live(api_client):
    response = await api_client.get("/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_ready_when_db_up(api_client):
    response = await api_client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_metrics_returns_prometheus_format(api_client):
    # сначала пингуем health чтобы метрика хотя бы один раз инкрементнулась
    await api_client.get("/health")
    response = await api_client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "ege_http_requests_total" in body
    assert "ege_http_request_duration_seconds" in body


@pytest.mark.asyncio
async def test_meta_version(api_client):
    response = await api_client.get("/api/v1/meta/version")
    assert response.status_code == 200
    body = response.json()
    assert body["api"] == "v1"
    assert "uptime_seconds" in body
    assert isinstance(body["version"], str)


@pytest.mark.asyncio
async def test_meta_features_lists_blocks(api_client):
    response = await api_client.get("/api/v1/meta/features")
    assert response.status_code == 200
    body = response.json()
    assert body["auth_email_password"] is True
    assert body["auth_telegram"] is True
    blocks = body["blocks"]
    # включённые в фазу 1
    for k in ("auth", "users", "catalog_meta", "problems", "attempts", "checking", "platform"):
        assert blocks[k] is True
    # отложены на фазу 2
    for k in ("variants", "analytics", "homework", "social", "notifications", "admin"):
        assert blocks[k] is False


@pytest.mark.asyncio
async def test_meta_limits_returns_constants(api_client):
    response = await api_client.get("/api/v1/meta/limits")
    assert response.status_code == 200
    body = response.json()
    assert body["password_min_length"] == 8
    assert body["subjects_min"] == 3
    assert body["subjects_max"] == 5
    assert "math" in body["subjects_known"]
    assert 10 in body["weekly_hours_options"] and 40 in body["weekly_hours_options"]
    assert body["access_token_ttl_minutes"] >= 1
    assert body["refresh_token_ttl_days"] >= 1
