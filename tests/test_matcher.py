import pytest

from app.models.schemas import ApplicantProfile
from app.services.matcher import match_grants


@pytest.mark.asyncio
async def test_match_grants_not_implemented():
    profile = ApplicantProfile(
        organisation_name="Acme Ltd",
        description="We develop AI tools for agriculture.",
    )
    with pytest.raises(NotImplementedError):
        await match_grants(profile, top_k=5)
