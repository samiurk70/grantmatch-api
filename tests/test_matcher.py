"""Unit tests for the matching pipeline components."""
import pytest

from app.models.schemas import ApplicantProfile
from app.utils.eligibility import check_eligibility
from app.utils.feature_extractor import extract_features, FEATURE_NAMES
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
# Eligibility
# ---------------------------------------------------------------------------

class _G:
    """Minimal grant stub for eligibility tests."""
    eligibility_org_types = None
    eligibility_regions = None
    eligibility_trl = None
    eligibility_sectors = None
    status = "open"
    description = None
    funding_min = None
    funding_max = None
    deadline = None


def test_eligibility_all_none_returns_likely_eligible():
    assert check_eligibility(_G(), PROFILE) == "likely_eligible"


def test_eligibility_org_type_mismatch():
    g = _G()
    g.eligibility_org_types = ["university"]
    assert check_eligibility(g, PROFILE) == "likely_ineligible"


def test_eligibility_org_type_match():
    g = _G()
    g.eligibility_org_types = ["sme", "startup"]
    assert check_eligibility(g, PROFILE) == "likely_eligible"


def test_eligibility_region_mismatch():
    g = _G()
    g.eligibility_regions = ["eu"]
    assert check_eligibility(g, PROFILE) == "likely_ineligible"


def test_eligibility_uk_covers_england():
    """A grant open to 'uk' should be eligible for an England-based applicant."""
    g = _G()
    g.eligibility_regions = ["uk"]
    assert check_eligibility(g, PROFILE) != "likely_ineligible"


def test_eligibility_trl_out_of_range():
    g = _G()
    g.eligibility_trl = [7, 9]   # high TRL, applicant is TRL 4
    assert check_eligibility(g, PROFILE) == "likely_ineligible"


def test_eligibility_no_sector_overlap_is_check_required():
    g = _G()
    g.eligibility_sectors = ["defence", "space"]
    assert check_eligibility(g, PROFILE) == "check_required"


# ---------------------------------------------------------------------------
# Feature extractor
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Reranker heuristic
# ---------------------------------------------------------------------------

def test_heuristic_score_range():
    reranker = GrantReranker()
    assert reranker.model is None, "No model should be present in test env"
    g = _G()
    features = extract_features(g, PROFILE, semantic_score=0.7)
    score, factors = reranker.score(g, PROFILE, 0.7, features)
    assert 0.0 <= score <= 100.0
    assert len(factors) == 3


def test_heuristic_perfect_score():
    """All features at 1.0 should yield the maximum heuristic score (100)."""
    reranker = GrantReranker()
    perfect = {k: 1.0 for k in FEATURE_NAMES}
    score, factors = reranker.score(_G(), PROFILE, 1.0, perfect)
    assert score == pytest.approx(100.0)
    assert len(factors) == 3


def test_heuristic_zero_score():
    reranker = GrantReranker()
    zeros = {k: 0.0 for k in FEATURE_NAMES}
    score, factors = reranker.score(_G(), PROFILE, 0.0, zeros)
    assert score == pytest.approx(0.0)
    assert len(factors) == 3
