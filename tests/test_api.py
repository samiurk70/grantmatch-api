import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

VALID_PROFILE = {
    "organisation_name": "Acme Ltd",
    "organisation_type": "sme",
    "description": "We develop AI-powered precision agriculture tools to reduce water usage in UK farms.",
    "sectors": ["ai", "agritech"],
    "location": "uk",
    "trl": 4,
    "top_n": 5,
}


# ---------------------------------------------------------------------------
# Health / root
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_root_returns_name():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/")
    assert response.status_code == 200
    assert response.json()["name"] == "GrantMatch API"


@pytest.mark.asyncio
async def test_health_full():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "model_loaded" in body
    assert "grants_in_db" in body
    assert "index_built" in body


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_requires_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/match", json=VALID_PROFILE)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_match_wrong_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/match",
            json=VALID_PROFILE,
            headers={"X-API-Key": "wrong"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid API key"


@pytest.mark.asyncio
async def test_grants_requires_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/grants")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_description_too_short():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad = {**VALID_PROFILE, "description": "too short"}
        response = await client.post(
            "/api/v1/match", json=bad, headers={"X-API-Key": "changeme"}
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_match_invalid_sector_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad = {**VALID_PROFILE, "sectors": ["not_a_real_sector"]}
        response = await client.post(
            "/api/v1/match", json=bad, headers={"X-API-Key": "changeme"}
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Match succeeds (empty DB → empty grants list)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_valid_request_returns_grants():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/match", json=VALID_PROFILE, headers={"X-API-Key": "changeme"}
        )
    assert response.status_code == 200
    body = response.json()
    assert "grants" in body
    assert "total_matched" in body
    assert "processing_time_ms" in body
    assert "data_freshness" in body
    assert isinstance(body["grants"], list)
    # Validate structure of any returned grants
    for grant in body["grants"]:
        assert 0.0 <= grant["score"] <= 100.0
        assert len(grant["top_factors"]) == 3


@pytest.mark.asyncio
async def test_match_respects_top_n():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        profile = {**VALID_PROFILE, "top_n": 3}
        response = await client.post(
            "/api/v1/match", json=profile, headers={"X-API-Key": "changeme"}
        )
    assert response.status_code == 200
    assert len(response.json()["grants"]) <= 3


# ---------------------------------------------------------------------------
# Grants browse
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grants_browse_open():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/grants?status=open", headers={"X-API-Key": "changeme"}
        )
    assert response.status_code == 200
    grants = response.json()
    assert isinstance(grants, list)
    for grant in grants:
        assert grant["status"] in ("open", "upcoming")


@pytest.mark.asyncio
async def test_grants_browse_returns_list():
    """Browse endpoint returns a JSON list (may be empty or populated depending on DB state)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/grants", headers={"X-API-Key": "changeme"}
        )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_grant_detail_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/grants/99999", headers={"X-API-Key": "changeme"}
        )
    assert response.status_code == 404
