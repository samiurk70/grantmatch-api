"""Rule-based eligibility checks — returns a verdict and the top factors."""
from __future__ import annotations

from typing import Literal

from app.models.db_models import Grant
from app.models.schemas import ApplicantProfile, FactorExplanation

EligibilityVerdict = Literal["likely_eligible", "check_required", "likely_ineligible"]


def check_eligibility(
    grant: Grant,
    profile: ApplicantProfile,
) -> tuple[EligibilityVerdict, list[FactorExplanation]]:
    """
    Run rule-based eligibility checks for a grant–profile pair.

    Returns a (verdict, factors) tuple where factors are the signals that
    drove the verdict, suitable for inclusion in GrantMatch.top_factors.
    """
    factors: list[FactorExplanation] = []

    # --- TRL range ---
    if grant.eligibility_trl and profile.trl is not None:
        trl_min, trl_max = grant.eligibility_trl[0], grant.eligibility_trl[-1]
        in_range = trl_min <= profile.trl <= trl_max
        factors.append(FactorExplanation(
            factor_name="trl_match",
            direction="positive" if in_range else "negative",
            impact=0.8 if in_range else 0.7,
        ))

    # --- Organisation type ---
    if grant.eligibility_org_types:
        org_match = profile.organisation_type in grant.eligibility_org_types
        factors.append(FactorExplanation(
            factor_name="org_type_match",
            direction="positive" if org_match else "negative",
            impact=0.9 if org_match else 0.8,
        ))

    # --- Sector overlap ---
    if grant.eligibility_sectors and profile.sectors:
        overlap = set(profile.sectors) & set(grant.eligibility_sectors)
        sector_match = bool(overlap)
        factors.append(FactorExplanation(
            factor_name="sector_overlap",
            direction="positive" if sector_match else "negative",
            impact=round(len(overlap) / max(len(profile.sectors), 1), 2),
        ))

    # --- Region ---
    if grant.eligibility_regions:
        region_match = (
            profile.location in grant.eligibility_regions
            or "international" in grant.eligibility_regions
        )
        factors.append(FactorExplanation(
            factor_name="region_match",
            direction="positive" if region_match else "negative",
            impact=0.85 if region_match else 0.75,
        ))

    # --- Derive verdict from negative signals ---
    negatives = sum(1 for f in factors if f.direction == "negative")
    if negatives == 0:
        verdict: EligibilityVerdict = "likely_eligible"
    elif negatives <= 1:
        verdict = "check_required"
    else:
        verdict = "likely_ineligible"

    return verdict, factors
