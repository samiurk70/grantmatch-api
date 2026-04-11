"""Builds a numeric feature vector for each (grant, profile) pair fed to the reranker."""
from __future__ import annotations

import numpy as np

from app.models.db_models import Grant
from app.models.schemas import ApplicantProfile, FactorExplanation


def build_feature_vector(
    grant: Grant,
    profile: ApplicantProfile,
    cosine_sim: float,
    factors: list[FactorExplanation],
) -> np.ndarray:
    """
    Return a 1-D float32 feature vector for XGBoost reranker input.

    Features (9 total):
      0  cosine_sim          — semantic similarity score from FAISS
      1  positive_signals    — count of positive eligibility factors
      2  negative_signals    — count of negative eligibility factors
      3  funding_max_log     — log1p(funding_max in GBP) or 0
      4  funding_min_log     — log1p(funding_min in GBP) or 0
      5  trl_distance        — abs diff between profile TRL and grant TRL midpoint (0 if unknown)
      6  sector_overlap      — fraction of profile sectors matching grant sectors
      7  org_type_match      — 1.0 if org type is in eligibility_org_types else 0.0
      8  region_match        — 1.0 if location is in eligibility_regions else 0.0
    """
    positives = sum(1 for f in factors if f.direction == "positive")
    negatives = sum(1 for f in factors if f.direction == "negative")

    funding_max_log = float(np.log1p(grant.funding_max or 0))
    funding_min_log = float(np.log1p(grant.funding_min or 0))

    if grant.eligibility_trl and profile.trl is not None:
        trl_mid = sum(grant.eligibility_trl) / len(grant.eligibility_trl)
        trl_distance = abs(profile.trl - trl_mid) / 9.0
    else:
        trl_distance = 0.0

    if grant.eligibility_sectors and profile.sectors:
        overlap = len(set(profile.sectors) & set(grant.eligibility_sectors))
        sector_overlap = overlap / max(len(profile.sectors), 1)
    else:
        sector_overlap = 0.0

    org_type_match = float(
        bool(grant.eligibility_org_types)
        and profile.organisation_type in grant.eligibility_org_types
    )

    region_match = float(
        bool(grant.eligibility_regions)
        and (
            profile.location in grant.eligibility_regions
            or "international" in grant.eligibility_regions
        )
    )

    return np.array(
        [
            cosine_sim,
            positives,
            negatives,
            funding_max_log,
            funding_min_log,
            trl_distance,
            sector_overlap,
            org_type_match,
            region_match,
        ],
        dtype=np.float32,
    )
