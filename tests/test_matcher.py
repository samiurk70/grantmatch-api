"""Unit tests for the matching pipeline components."""
import pytest

from app.models.schemas import ApplicantProfile
from app.utils.eligibility import check_eligibility
from app.utils.feature_extractor import extract_features, FEATURE_NAMES, _sector_jaccard
from app.services.reranker import GrantReranker


PROFILE = ApplicantProfile(
    organisation_name="Acme Ltd",
    organisation_type="sme",
    description="We develop AI-powered precision agriculture tools to reduce water usage.",
    sectors=["ai", "agritech"],
    location="england",
    trl=4,
)


# ---------------------------------------------------------------------------
# Grant stub
# ---------------------------------------------------------------------------

class _G:
    """Minimal grant stub for unit tests — mirrors the Grant ORM interface."""
    eligibility_org_types = None
    eligibility_regions = None
    eligibility_trl = None
    eligibility_sectors = None
    status = "open"
    description = None
    funding_min = None
    funding_max = None
    deadline = None


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

def test_eligibility_org_type_mismatch():
    g = _G()
    g.eligibility_org_types = ["university"]
    assert check_eligibility(g, PROFILE) == "likely_ineligible"


def test_eligibility_region_mismatch():
    g = _G()
    g.eligibility_regions = ["eu"]
    # England is not in the EU-only region list
    assert check_eligibility(g, PROFILE) == "likely_ineligible"


def test_eligibility_full_match():
    g = _G()
    g.eligibility_org_types = ["sme", "startup"]
    g.eligibility_regions = ["uk"]
    g.eligibility_trl = [3, 6]
    g.eligibility_sectors = ["ai", "agritech"]
    assert check_eligibility(g, PROFILE) == "likely_eligible"


def test_eligibility_all_none_returns_likely_eligible():
    assert check_eligibility(_G(), PROFILE) == "likely_eligible"


def test_eligibility_org_type_match():
    g = _G()
    g.eligibility_org_types = ["sme", "startup"]
    assert check_eligibility(g, PROFILE) == "likely_eligible"


def test_eligibility_uk_covers_england():
    g = _G()
    g.eligibility_regions = ["uk"]
    assert check_eligibility(g, PROFILE) != "likely_ineligible"


def test_eligibility_trl_out_of_range():
    g = _G()
    g.eligibility_trl = [7, 9]
    assert check_eligibility(g, PROFILE) == "likely_ineligible"


def test_eligibility_no_sector_overlap_is_check_required():
    g = _G()
    g.eligibility_sectors = ["defence", "space"]
    assert check_eligibility(g, PROFILE) == "check_required"


# ---------------------------------------------------------------------------
# Feature extractor
# ---------------------------------------------------------------------------

def test_feature_extractor_keys():
    g = _G()
    features = extract_features(g, PROFILE, semantic_score=0.7)
    assert set(features.keys()) == set(FEATURE_NAMES)


def test_extract_features_returns_all_keys():
    g = _G()
    features = extract_features(g, PROFILE, semantic_score=0.7)
    assert set(features.keys()) == set(FEATURE_NAMES)


def test_extract_features_values_in_range():
    g = _G()
    features = extract_features(g, PROFILE, semantic_score=0.5)
    for k, v in features.items():
        assert 0.0 <= v <= 1.0, f"Feature {k!r} out of range: {v}"


def test_semantic_similarity_passthrough():
    g = _G()
    features = extract_features(g, PROFILE, semantic_score=0.82)
    assert features["semantic_similarity"] == pytest.approx(0.82)


def test_is_open_for_closed_grant():
    g = _G()
    g.status = "closed"
    features = extract_features(g, PROFILE, semantic_score=0.5)
    assert features["is_open"] == 0.0


def test_sector_overlap_identical():
    """Profile sectors == grant sectors should give sector_overlap == 1.0 (Jaccard)."""
    # When A == B, |A ∩ B| / |A ∪ B| == 1.0
    overlap = _sector_jaccard(["ai", "agritech"], ["ai", "agritech"])
    assert overlap == pytest.approx(1.0)


def test_funding_fit_within_range():
    """funding_needed within [funding_min, funding_max] should yield funding_fit == 1.0."""
    profile_with_funding = ApplicantProfile(
        organisation_name="Test Org",
        organisation_type="sme",
        description="We develop AI-powered precision agriculture tools to reduce water usage.",
        sectors=["ai"],
        location="uk",
        trl=4,
        funding_needed=100_000,
    )
    g = _G()
    g.funding_min = 50_000
    g.funding_max = 500_000
    features = extract_features(g, profile_with_funding, semantic_score=0.5)
    assert features["funding_fit"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Reranker heuristic
# ---------------------------------------------------------------------------

def test_heuristic_score_range():
    reranker = GrantReranker()
    reranker.model = None  # force heuristic path regardless of whether model.pkl exists
    g = _G()
    features = extract_features(g, PROFILE, semantic_score=0.7)
    score, factors = reranker.score(g, PROFILE, 0.7, features)
    assert 0.0 <= score <= 100.0
    assert len(factors) == 3


def test_heuristic_perfect_score():
    reranker = GrantReranker()
    reranker.model = None  # force heuristic path
    perfect = {k: 1.0 for k in FEATURE_NAMES}
    score, factors = reranker.score(_G(), PROFILE, 1.0, perfect)
    assert score == pytest.approx(100.0)
    assert len(factors) == 3


def test_heuristic_zero_score():
    reranker = GrantReranker()
    reranker.model = None  # force heuristic path
    zeros = {k: 0.0 for k in FEATURE_NAMES}
    score, factors = reranker.score(_G(), PROFILE, 0.0, zeros)
    assert score == pytest.approx(0.0)
    assert len(factors) == 3
