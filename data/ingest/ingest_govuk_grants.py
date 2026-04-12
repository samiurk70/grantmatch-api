"""
Ingest UK government grants from GOV.UK Find a Grant.

Standalone usage:
    python -m data.ingest.ingest_govuk_grants

The service has no public API — we scrape the HTML listing page and
follow pagination via ?skip=N&limit=10 query parameters.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
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

# Mapping of description keywords → eligibility org types
_ORG_TYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsme\b|small.and.medium|small business", re.I), "sme"),
    (re.compile(r"\bstartup\b|\bstart.up\b", re.I), "startup"),
    (re.compile(r"\buniversit|\bacademi|\bresearch.institution", re.I), "university"),
    (re.compile(r"\bcharity\b|\bcharities\b|\bvoluntary\b|\bvcse\b|\bngo\b", re.I), "charity"),
    (re.compile(r"\blarge.compan|\bcorporat|\bmultinational", re.I), "large_company"),
    (re.compile(r"\bindividual\b|\bsole.trader\b|\bfreelance", re.I), "individual"),
]


def _slugify(text: str) -> str:
    """Convert a grant title to a stable slug for use as external_id."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:190]


def _parse_deadline(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    for fmt in ("%d %B %Y", "%d/%m/%Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _extract_org_types(text: str) -> list[str]:
    found: list[str] = []
    for pattern, org_type in _ORG_TYPE_PATTERNS:
        if pattern.search(text):
            found.append(org_type)
    # Default: if nothing specific found, open to most types
    return found or ["sme", "large_company", "university", "charity"]


def _derive_status(deadline: datetime | None) -> str:
    if deadline is None:
        return "open"
    return "open" if deadline > datetime.utcnow() else "closed"


def _parse_grant_card(card: BeautifulSoup, base_url: str) -> dict | None:
    """Extract fields from a single grant listing card element."""
    try:
        title_el = card.select_one("h2 a, h3 a, .grant-title a, a.govuk-link")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        url = href if href.startswith("http") else f"{base_url}{href}"
        external_id = _slugify(title)

        description = ""
        desc_el = card.select_one("p.govuk-body, .grant-summary, p")
        if desc_el:
            description = desc_el.get_text(strip=True)

        funder = ""
        funder_el = card.select_one(".grant-funder, [data-funder]")
        if funder_el:
            funder = funder_el.get_text(strip=True)

        deadline_text = ""
        deadline_el = card.select_one(".grant-deadline, [data-deadline], time")
        if deadline_el:
            deadline_text = deadline_el.get("datetime") or deadline_el.get_text(strip=True)

        deadline = _parse_deadline(deadline_text)
        status = _derive_status(deadline)

        full_text = f"{title} {description}"
        return dict(
            source="govuk",
            external_id=external_id,
            title=title[:500],
            description=description or None,
            summary=description[:200] if description else None,
            funder=funder or "UK Government",
            programme=None,
            funding_min=None,
            funding_max=None,
            deadline=deadline,
            open_date=None,
            status=status,
            eligibility_org_types=_extract_org_types(full_text),
            eligibility_sectors=extract_sectors_from_text(full_text),
            eligibility_regions=["uk"],
            eligibility_trl=None,
            url=url,
        )
    except Exception as exc:
        logger.warning("Failed to parse grant card: %s", exc)
        return None


async def _fetch_page(
    client: httpx.AsyncClient, skip: int
) -> BeautifulSoup | None:
    params = {"skip": skip, "limit": PAGE_SIZE}
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = await client.get(
                f"{BASE_URL}{GRANTS_PATH}", params=params
            )
            response.raise_for_status()
            return BeautifulSoup(response.text, "lxml")
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning(
                "GOV.UK page skip=%d attempt %d/%d failed: %s",
                skip, attempt, RETRY_ATTEMPTS, exc,
            )
            await asyncio.sleep(2 ** attempt)
    logger.error("Giving up on GOV.UK skip=%d: %s", skip, last_exc)
    return None


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


async def ingest_govuk_grants(db_session: AsyncSession) -> int:
    """
    Scrape GOV.UK Find a Grant and upsert Grant rows.

    Returns the total number of records processed.
    """
    total = 0

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "GrantMatch-Ingest/1.0 (research tool)"},
    ) as client:
        skip = 0
        while True:
            soup = await _fetch_page(client, skip)
            if soup is None:
                break

            # The service uses several possible card selectors across versions
            cards = (
                soup.select("li.grants-list__item")
                or soup.select("div.grant-card")
                or soup.select("article")
            )

            if not cards:
                logger.info("GOV.UK: no grant cards found at skip=%d, stopping.", skip)
                break

            for card in cards:
                data = _parse_grant_card(card, BASE_URL)
                if data:
                    await _upsert(db_session, data)
                    total += 1

            await db_session.commit()
            logger.info("GOV.UK: upserted %d records so far (skip=%d).", total, skip)

            # Check for a "next page" link; stop if absent
            next_link = soup.select_one("a[rel='next'], .govuk-pagination__next a")
            if not next_link and len(cards) < PAGE_SIZE:
                break

            skip += PAGE_SIZE

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
