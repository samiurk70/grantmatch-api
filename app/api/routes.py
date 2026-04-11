from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import get_settings
from app.models.schemas import ApplicantProfile, MatchResponse
from app.services.matcher import match_grants

router = APIRouter()

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    if api_key != get_settings().api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


@router.post("/match", response_model=MatchResponse, dependencies=[Depends(verify_api_key)])
async def match(profile: ApplicantProfile) -> MatchResponse:
    """Accept an applicant profile and return ranked grant matches."""
    return await match_grants(profile, profile.top_n or 10)
