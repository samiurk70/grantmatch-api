"""Extracts a named feature dict for each (grant, profile) pair."""
from __future__ import annotations

from datetime import datetime

from app.models.db_models import Grant
from app.models.schemas import ApplicantProfile

# Canonical feature order — must match ml/train.py when building training matrix
FEATURE_NAMES: list[str] = [
    "semantic_similarity",
    "sector_overlap",
    "org_type_match",
    "trl_match",
    "region_match",
    "is_open",
    "days_to_deadline",
    "funding_fit",
    "description_length",
]

_UK_LOCATIONS = frozenset(["uk", "england", "scotland", "wales", "northern_ireland"])


def _sector_jaccard(profile_sectors: list[str], grant_sectors: list | None) -> float:
    if not grant_sectors or not profile_sectors:
        return 0.5   # unknown → neutral (same logic as org_type and trl)
    a, b = set(profile_sectors), set(grant_sectors)
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _org_type_score(profile_org: str, grant_org_types: list | None) -> float:
    if not grant_org_types:
        return 0.5   # no restriction known → uncertain
    return 1.0 if profile_org in grant_org_types else 0.0


def _trl_score(profile_trl: int | None, grant_trl: list | None) -> float:
    if profile_trl is None or not grant_trl:
        return 0.5   # unknown → uncertain
    trl_min, trl_max = grant_trl[0], grant_trl[-1]
    return 1.0 if trl_min <= profile_trl <= trl_max else 0.0


def _region_score(profile_location: str, grant_regions: list | None) -> float:
    if not grant_regions:
        return 0.5
    regions = set(grant_regions)
    if "international" in regions or profile_location in regions:
        return 1.0
    if "uk" in regions and profile_location in _UK_LOCATIONS:
        return 1.0
    if profile_location == "uk" and regions & _UK_LOCATIONS:
        return 1.0
    return 0.0


def _days_to_deadline_score(deadline: datetime | None) -> float:
    if deadline is None:
        return 0.5
    delta = (deadline - datetime.utcnow()).days
    if delta <= 0:
        return 0.0
    return min(delta / 180.0, 1.0)


def _funding_fit_score(
    funding_needed: float | None,
    funding_min: float | None,
    funding_max: float | None,
) -> float:
    if funding_needed is None or (funding_min is None and funding_max is None):
        return 0.5
    if funding_max is not None and funding_needed > funding_max:
        return 0.0
    if funding_min is not None and funding_needed < funding_min:
        return 0.2   # asking for less than the minimum — unlikely to qualify
    return 1.0


def _description_length_score(description: str | None) -> float:
    if not description:
        return 0.0
    word_count = len(description.split())
    return min(word_count / 500.0, 1.0)


def extract_features(
    grant: Grant,
    profile: ApplicantProfile,
    semantic_score: float,
) -> dict[str, float]:
    """
    Build a named feature dict for one (grant, profile) pair.

    semantic_score: cosine similarity from FAISS (0–1, already normalised).
    All returned values are floats in [0, 1].
    """
    return {
        "semantic_similarity": float(max(0.0, min(1.0, semantic_score))),
        "sector_overlap":      _sector_jaccard(profile.sectors, grant.eligibility_sectors),
        "org_type_match":      _org_type_score(profile.organisation_type, grant.eligibility_org_types),
        "trl_match":           _trl_score(profile.trl, grant.eligibility_trl),
        "region_match":        _region_score(profile.location, grant.eligibility_regions),
        "is_open":             1.0 if grant.status in ("open", "upcoming") else 0.0,
        "days_to_deadline":    _days_to_deadline_score(grant.deadline),
        "funding_fit":         _funding_fit_score(
                                   profile.funding_needed,
                                   grant.funding_min,
                                   grant.funding_max,
                               ),
        "description_length":  _description_length_score(grant.description),
    }


def features_to_array(features: dict[str, float]):
    """Convert a feature dict to a float32 numpy array in FEATURE_NAMES order."""
    import numpy as np
    return np.array([features[k] for k in FEATURE_NAMES], dtype=np.float32)
