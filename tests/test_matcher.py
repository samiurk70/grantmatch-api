import pytest

from app.models.schemas import ApplicantProfile
from app.services.matcher import match_grants


PROFILE = ApplicantProfile(
    organisation_name="Acme Ltd",
    organisation_type="sme",
    description="We develop AI-powered precision agriculture tools to reduce water usage.",
    sectors=["ai", "agritech"],
    location="england",
    trl=4,
)


@pytest.mark.asyncio
async def test_match_grants_not_implemented():
    with pytest.raises(NotImplementedError):
        await match_grants(PROFILE, top_k=5)
