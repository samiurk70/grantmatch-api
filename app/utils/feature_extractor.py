"""Builds a feature vector for each (grant, profile) pair fed to the reranker."""
from __future__ import annotations

import numpy as np

from app.models.db_models import Grant
from app.models.schemas import ApplicantProfile, EligibilitySignal


def build_feature_vector(
    grant: Grant,
    profile: ApplicantProfile,
    cosine_sim: float,
    eligibility_signals: list[EligibilitySignal],
) -> np.ndarray:
    """Return a 1-D numpy feature vector for reranker input."""
    eligible_count = sum(1 for s in eligibility_signals if s.met)
    ineligible_count = sum(1 for s in eligibility_signals if not s.met)

    features = [
        cosine_sim,
        eligible_count,
        ineligible_count,
        float(grant.max_award_gbp or 0),
        float(profile.trl or 0),
        float(grant.trl_min or 0),
        float(grant.trl_max or 9),
    ]
    return np.array(features, dtype=np.float32)
