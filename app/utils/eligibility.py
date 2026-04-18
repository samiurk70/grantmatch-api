"""Rule-based eligibility filter — returns a single verdict string."""
from __future__ import annotations

from typing import Literal

from app.models.db_models import Grant
from app.models.schemas import ApplicantProfile

EligibilityVerdict = Literal["likely_eligible", "check_required", "likely_ineligible"]

# All location values that count as "UK" for region compatibility checks
_UK_LOCATIONS = frozenset(["uk", "england", "scotland", "wales", "northern_ireland"])


def _location_compatible(profile_location: str, grant_regions: list) -> bool:
    """Return True if the applicant's location satisfies the grant's region list."""
    regions = set(grant_regions)
    if not regions:
        return True
    if "international" in regions:
        return True
    if profile_location in regions:
        return True
    # "uk" in the grant covers all UK sub-regions
    if "uk" in regions and profile_location in _UK_LOCATIONS:
        return True
    # applicant is "uk" — compatible with any grant that lists a UK region
    if profile_location == "uk" and regions & _UK_LOCATIONS:
        return True
    return False


def check_eligibility(grant: Grant, profile: ApplicantProfile) -> EligibilityVerdict:
    """
    Apply hard eligibility rules in order of severity.

    Returns one of:
      "likely_ineligible" — a hard rule is violated; skip this grant
      "check_required"    — soft mismatch (sector gap); worth reviewing
      "likely_eligible"   — passes all checks
    """
    # --- Organisation type ---
    # Downgraded from hard "ineligible" to "check_required" because real grant records
    # often have incomplete eligibility_org_types data (especially CORDIS/GtR), causing
    # false hard-drops for valid applicant types like charity and individual.
    if grant.eligibility_org_types and profile.organisation_type not in grant.eligibility_org_types:
        return "check_required"

    # --- Region ---
    if grant.eligibility_regions and not _location_compatible(
        profile.location, grant.eligibility_regions
    ):
        return "likely_ineligible"

    # --- TRL range ---
    if grant.eligibility_trl and profile.trl is not None:
        trl_min = grant.eligibility_trl[0]
        trl_max = grant.eligibility_trl[-1]
        if profile.trl < trl_min or profile.trl > trl_max:
            return "likely_ineligible"

    # --- Sector overlap (soft check) ---
    if grant.eligibility_sectors and profile.sectors:
        overlap = set(profile.sectors) & set(grant.eligibility_sectors)
        if not overlap:
            return "check_required"

    return "likely_eligible"
