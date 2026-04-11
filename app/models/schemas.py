from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ---------- Request ----------

class ApplicantProfile(BaseModel):
    organisation_name: str = Field(..., description="Name of the applying organisation")
    description: str = Field(..., description="Project or company description (used for semantic matching)")
    sector: Optional[str] = Field(None, description="Primary sector, e.g. 'cleantech', 'medtech'")
    trl: Optional[int] = Field(None, ge=1, le=9, description="Current Technology Readiness Level (1-9)")
    region: Optional[str] = Field(None, description="Applicant region: 'UK', 'EU', or leave blank for both")
    max_grant_size_gbp: Optional[float] = Field(None, description="Maximum grant size of interest (GBP)")


class MatchRequest(BaseModel):
    profile: ApplicantProfile
    top_k: int = Field(10, ge=1, le=50)


# ---------- Response ----------

class EligibilitySignal(BaseModel):
    rule: str
    met: bool
    detail: Optional[str] = None


class ShapExplanation(BaseModel):
    feature: str
    contribution: float


class GrantMatch(BaseModel):
    grant_id: int
    external_id: str
    title: str
    funder: Optional[str]
    max_award_gbp: Optional[float]
    deadline: Optional[date]
    url: Optional[str]
    fit_score: float = Field(..., ge=0.0, le=1.0)
    eligibility_signals: list[EligibilitySignal]
    shap_explanations: list[ShapExplanation]


class MatchResponse(BaseModel):
    matches: list[GrantMatch]
    model_version: str


# ---------- Misc ----------

class HealthResponse(BaseModel):
    status: str
