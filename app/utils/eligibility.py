"""Rule-based eligibility checks for each grant type."""
from __future__ import annotations

from app.models.db_models import Grant
from app.models.schemas import ApplicantProfile, EligibilitySignal


def check_eligibility(grant: Grant, profile: ApplicantProfile) -> list[EligibilitySignal]:
    """Return a list of eligibility signals for a grant-profile pair."""
    signals: list[EligibilitySignal] = []

    # TRL range check
    if grant.trl_min is not None and profile.trl is not None:
        met = profile.trl >= grant.trl_min
        signals.append(EligibilitySignal(
            rule="trl_min",
            met=met,
            detail=f"Required TRL >= {grant.trl_min}, applicant TRL = {profile.trl}",
        ))

    if grant.trl_max is not None and profile.trl is not None:
        met = profile.trl <= grant.trl_max
        signals.append(EligibilitySignal(
            rule="trl_max",
            met=met,
            detail=f"Required TRL <= {grant.trl_max}, applicant TRL = {profile.trl}",
        ))

    # Region check
    if grant.region and profile.region:
        met = grant.region.lower() in ("both", profile.region.lower())
        signals.append(EligibilitySignal(
            rule="region",
            met=met,
            detail=f"Grant region: {grant.region}, applicant region: {profile.region}",
        ))

    # Award size check
    if grant.max_award_gbp is not None and profile.max_grant_size_gbp is not None:
        met = grant.max_award_gbp <= profile.max_grant_size_gbp
        signals.append(EligibilitySignal(
            rule="award_size",
            met=met,
            detail=f"Grant max award: £{grant.max_award_gbp:,.0f}, requested max: £{profile.max_grant_size_gbp:,.0f}",
        ))

    return signals
