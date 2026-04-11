import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


VALID_PROFILE = {
    "organisation_name": "Acme Ltd",
    "organisation_type": "sme",
    "description": "We develop AI-powered precision agriculture tools to reduce water usage.",
    "sectors": ["ai", "agritech"],
    "location": "england",
    "trl": 4,
    "top_n": 5,
}


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
async def test_match_invalid_sector_rejected():
    """Pydantic should reject unknown sectors before the route handler runs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad_profile = {**VALID_PROFILE, "sectors": ["not_a_real_sector"]}
        response = await client.post(
            "/api/v1/match",
            json=bad_profile,
            headers={"X-API-Key": "changeme"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_match_description_too_short_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad_profile = {**VALID_PROFILE, "description": "too short"}
        response = await client.post(
            "/api/v1/match",
            json=bad_profile,
            headers={"X-API-Key": "changeme"},
        )
    assert response.status_code == 422
