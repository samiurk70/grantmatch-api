from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

ALLOWED_SECTORS = frozenset([
    "ai", "healthcare", "clean_energy", "manufacturing", "net_zero",
    "digital", "biotech", "agritech", "fintech", "defence", "education",
    "transport", "space", "quantum", "cybersecurity", "climate", "social",
    "arts", "other",
])

OrgType = Literal[
    "sme", "university", "charity", "large_company", "individual", "startup"
]

Location = Literal[
    "england", "scotland", "wales", "northern_ireland", "uk", "eu"
]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ApplicantProfile(BaseModel):
    organisation_name: Optional[str] = Field(
        None, description="Name of the applying organisation"
    )
    organisation_type: OrgType = Field(
        ..., description="Type of organisation"
    )
    description: str = Field(
        ...,
        min_length=50,
        description="Project or research description (min 50 chars, used for semantic matching)",
    )
    sectors: list[str] = Field(
        ...,
        description=(
            "Relevant sectors — must be drawn from the allowed list: "
            + ", ".join(sorted(ALLOWED_SECTORS))
        ),
    )
    location: Location = Field(
        ..., description="Applicant location"
    )
    trl: Optional[Annotated[int, Field(ge=1, le=9)]] = Field(
        None, description="Current Technology Readiness Level (1–9)"
    )
    funding_needed: Optional[float] = Field(
        None, gt=0, description="Approximate funding needed in GBP"
    )
    top_n: Optional[Annotated[int, Field(ge=1, le=20)]] = Field(
        10, description="Maximum number of results to return (max 20)"
    )

    @field_validator("sectors")
    @classmethod
    def sectors_must_be_valid(cls, v: list[str]) -> list[str]:
        invalid = [s for s in v if s not in ALLOWED_SECTORS]
        if invalid:
            raise ValueError(
                f"Unknown sector(s): {invalid}. "
                f"Allowed values: {sorted(ALLOWED_SECTORS)}"
            )
        if not v:
            raise ValueError("sectors must contain at least one entry")
        return v


# ---------------------------------------------------------------------------
# Response sub-schemas
# ---------------------------------------------------------------------------

class FactorExplanation(BaseModel):
    factor_name: str
    direction: Literal["positive", "negative"]
    impact: float = Field(..., ge=0.0, le=1.0)


class GrantMatch(BaseModel):
    grant_id: int
    title: str
    funder: str
    programme: Optional[str] = None
    summary: str
    score: float = Field(..., ge=0.0, le=100.0, description="Match score 0–100")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence 0–1")
    deadline: Optional[datetime] = None
    status: str
    funding_range: str = Field(
        ..., description="Human-readable funding range, e.g. '£50k – £500k' or 'Unknown'"
    )
    eligibility_verdict: Literal["likely_eligible", "check_required", "likely_ineligible"]
    top_factors: Annotated[list[FactorExplanation], Field(min_length=3, max_length=3)]
    url: Optional[str] = None


# ---------------------------------------------------------------------------
# Top-level response schemas
# ---------------------------------------------------------------------------

class MatchResponse(BaseModel):
    profile_summary: str = Field(
        ..., description="First 100 chars of the submitted description"
    )
    total_matched: int
    grants: list[GrantMatch]
    processing_time_ms: float
    data_freshness: str = Field(
        ..., description="ISO date of last data ingestion, e.g. '2024-11-01'"
    )


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    grants_in_db: int
    index_built: bool
    last_ingestion: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ---------------------------------------------------------------------------
# Grant browse schema (lightweight — no score or factors)
# ---------------------------------------------------------------------------

class GrantSummary(BaseModel):
    grant_id: int
    title: str
    funder: str
    programme: Optional[str] = None
    summary: Optional[str] = None
    status: str
    funding_range: str
    deadline: Optional[datetime] = None
    url: Optional[str] = None
    eligibility_regions: Optional[list[str]] = None
    eligibility_sectors: Optional[list[str]] = None
