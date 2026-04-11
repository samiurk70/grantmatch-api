"""Core matching pipeline: embed profile → FAISS ANN search → rerank."""
from __future__ import annotations

import numpy as np

from app.config import get_settings
from app.models.schemas import ApplicantProfile, GrantMatch, MatchResponse

# Placeholder — full implementation added in a later step.


async def match_grants(profile: ApplicantProfile, top_k: int) -> MatchResponse:
    """Return top-k grant matches for the given applicant profile."""
    raise NotImplementedError("Matcher not yet implemented")
