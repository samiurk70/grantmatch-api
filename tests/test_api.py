import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import get_settings


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_match_requires_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/match",
            json={
                "profile": {
                    "organisation_name": "Acme Ltd",
                    "description": "We develop AI tools for agriculture.",
                },
                "top_k": 5,
            },
        )
    assert response.status_code == 403
