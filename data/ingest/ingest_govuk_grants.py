"""
Ingest UK government grants from GOV.UK Find a Grant.

Standalone usage:
    python -m data.ingest.ingest_govuk_grants

The service is a Next.js application — grant data is embedded as JSON in
the __NEXT_DATA__ script tag on each listing page. No HTML card parsing is
needed. Pagination uses ?page=N query parameter, 10 results per page.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from math import ceil

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, create_all_tables
from app.models.db_models import Grant
from data.ingest import extract_sectors_from_text

logger = logging.getLogger(__name__)

BASE_URL = "https://www.find-government-grants.service.gov.uk"
GRANTS_PATH = "/grants"
PAGE_SIZE = 10
REQUEST_TIMEOUT = 30.0
RETRY_ATTEMPTS = 3

# ---------------------------------------------------------------------------
# Field mappings
# ---------------------------------------------------------------------------

# grantApplicantType values → our org type codes
_APPLICANT_TYPE_MAP: dict[str, list[str]] = {
    "Personal / Individual": ["individual"],
    "Non-profit":            ["charity"],
    "Private Sector":        ["sme", "startup", "large_company"],
    "Public Sector":         [],   # no equivalent in our schema
    "Local authority":       [],
}

# grantLocation values → our region codes
_LOCATION_MAP: dict[str, str] = {
    "England":            "england",
    "North East England": "england",
    "North West England": "england",
    "South East England": "england",
    "South West England": "england",
    "Midlands":           "england",
    "Scotland":           "scotland",
    "Wales":              "wales",
    "Northern Ireland":   "northern_ireland",
    "National":           "uk",
}


def _map_org_types(applicant_types: list[str]) -> list[str]:
    result: list[str] = []
    for t in applicant_types:
        result.extend(_APPLICANT_TYPE_MAP.get(t, []))
    seen: set[str] = set()
    deduped: list[str] = []
    for x in result:
        if x not in seen:
            seen.add(x)
            deduped.append(x)
    return deduped or ["sme", "university", "charity", "large_company"]


def _map_regions(locations: list[str]) -> list[str]:
    regions: set[str] = set()
    for loc in locations:
        code = _LOCATION_MAP.get(loc)
        if code:
            regions.add(code)
    if not regions:
        return ["uk"]
    # If all four sub-regions of UK appear, collapse to "uk"
    uk_sub = {"england", "scotland", "wales", "northern_ireland"}
    if uk_sub.issubset(regions):
        return ["uk"]
    return sorted(regions)


def _parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def _derive_status(deadline: datetime | None) -> str:
    if deadline is None:
        return "open"
    return "open" if deadline > datetime.utcnow() else "closed"


def _build_grant(item: dict) -> dict | None:
    """Map one __NEXT_DATA__ grant item to Grant column kwargs."""
    name = (item.get("grantName") or "").strip()
    label = (item.get("label") or "").strip()
    if not name or not label:
        return None

    description = (item.get("grantShortDescription") or "").strip()
    funder = (item.get("grantFunder") or "UK Government").strip()

    funding_min = item.get("grantMinimumAward")
    funding_max = item.get("grantMaximumAward")
    try:
        funding_min = float(funding_min) if funding_min is not None else None
        funding_max = float(funding_max) if funding_max is not None else None
    except (TypeError, ValueError):
        funding_min = funding_max = None

    open_date = _parse_iso_date(item.get("grantApplicationOpenDate"))
    deadline = _parse_iso_date(item.get("grantApplicationCloseDate"))
    status = _derive_status(deadline)

    org_types = _map_org_types(item.get("grantApplicantType") or [])
    regions = _map_regions(item.get("grantLocation") or [])

    full_text = f"{name} {description}"
    url = f"{BASE_URL}{GRANTS_PATH}/{label}"

    return dict(
        source="govuk",
        external_id=label,
        title=name[:500],
        description=description or None,
        summary=description[:200] if description else None,
        funder=funder,
        programme=None,
        funding_min=funding_min,
        funding_max=funding_max,
        open_date=open_date,
        deadline=deadline,
        status=status,
        eligibility_org_types=org_types,
        eligibility_sectors=extract_sectors_from_text(full_text),
        eligibility_regions=regions,
        eligibility_trl=None,
        url=url,
    )


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def _fetch_page(client: httpx.AsyncClient, page: int) -> dict | None:
    """Fetch one listing page and return the parsed __NEXT_DATA__ props."""
    params = {"page": page} if page > 1 else {}
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = await client.get(f"{BASE_URL}{GRANTS_PATH}", params=params)
            response.raise_for_status()
            # Extract __NEXT_DATA__ JSON embedded in the page
            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                response.text,
                re.DOTALL,
            )
            if not match:
                logger.warning("No __NEXT_DATA__ found on page %d", page)
                return None
            data = json.loads(match.group(1))
            return data.get("props", {}).get("pageProps", {})
        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
            last_exc = exc
            logger.warning("GOV.UK page %d attempt %d/%d failed: %s", page, attempt, RETRY_ATTEMPTS, exc)
            await asyncio.sleep(2 ** attempt)
    logger.error("Giving up on GOV.UK page %d: %s", page, last_exc)
    return None


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

async def _upsert(session: AsyncSession, data: dict) -> None:
    result = await session.execute(
        select(Grant).where(Grant.external_id == data["external_id"])
    )
    existing = result.scalar_one_or_none()
    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
    else:
        session.add(Grant(**data))


# ---------------------------------------------------------------------------
# Main ingest function
# ---------------------------------------------------------------------------

async def ingest_govuk_grants(db_session: AsyncSession) -> int:
    """
    Scrape GOV.UK Find a Grant via embedded __NEXT_DATA__ JSON and upsert
    Grant rows.

    Returns the total number of records processed.
    """
    total = 0
    total_grants = None
    page = 1

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "GrantMatch-Ingest/1.0 (research tool)"},
    ) as client:
        while True:
            props = await _fetch_page(client, page)
            if props is None:
                break

            if total_grants is None:
                total_grants = props.get("totalGrants", 0)
                total_pages = ceil(total_grants / PAGE_SIZE)
                logger.info("GOV.UK: %d grants across %d pages.", total_grants, total_pages)

            items = props.get("searchResult", [])
            if not items:
                logger.info("GOV.UK: no items on page %d, stopping.", page)
                break

            for item in items:
                data = _build_grant(item)
                if data:
                    await _upsert(db_session, data)
                    total += 1

            await db_session.commit()
            logger.info("GOV.UK: page %d done — %d records upserted so far.", page, total)

            # Stop when we've fetched all pages
            if total_grants and total >= total_grants:
                break
            if len(items) < PAGE_SIZE:
                break
            page += 1

    logger.info("GOV.UK ingestion complete: %d records total.", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    async def _main() -> None:
        await create_all_tables()
        async with AsyncSessionLocal() as session:
            count = await ingest_govuk_grants(session)
        print(f"Done — {count} GOV.UK grant records upserted.")

    asyncio.run(_main())
