"""
Ingest live Innovate UK / UKRI competitions from the UKRI Opportunities page.

Standalone usage:
    python -m data.ingest.ingest_ukri_opportunities

We scrape the listing page for opportunity cards, then follow each
card's detail link to fetch the full description.
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

from app.config import get_settings
from app.database import AsyncSessionLocal, create_all_tables
from app.models.db_models import Grant
from data.ingest import extract_sectors_from_text

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30.0
RETRY_ATTEMPTS = 3
DETAIL_CONCURRENCY = 5  # simultaneous detail-page fetches


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:190]


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text.strip())
    for fmt in ("%d %B %Y", "%B %d, %Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_gbp(text: str | None) -> float | None:
    """Extract a numeric GBP amount from a string like '£2.5 million' or '£500,000'."""
    if not text:
        return None
    text = text.replace(",", "").lower()
    match = re.search(r"£\s*([\d.]+)\s*(m(?:illion)?|k(?:illion)?|b(?:illion)?)?", text)
    if not match:
        return None
    amount = float(match.group(1))
    suffix = (match.group(2) or "").lower()
    if suffix.startswith("b"):
        amount *= 1_000_000_000
    elif suffix.startswith("m"):
        amount *= 1_000_000
    elif suffix.startswith("k"):
        amount *= 1_000
    return amount


def _derive_status(open_date: datetime | None, close_date: datetime | None) -> str:
    now = datetime.utcnow()
    if close_date and close_date < now:
        return "closed"
    if open_date and open_date > now:
        return "upcoming"
    return "open"


async def _fetch_html(
    client: httpx.AsyncClient, url: str, label: str = ""
) -> BeautifulSoup | None:
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = await client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "lxml")
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning("Fetch %s attempt %d/%d failed: %s", label or url, attempt, RETRY_ATTEMPTS, exc)
            await asyncio.sleep(2 ** attempt)
    logger.error("Giving up on %s: %s", label or url, last_exc)
    return None


def _extract_funder(soup: BeautifulSoup) -> str:
    """Try several selectors to find the funder name on a UKRI detail page."""
    for selector in [
        "[data-funder]",
        ".opportunity-funder",
        ".meta-item--funder",
    ]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)
    # Fall back: look for "Funder:" label text
    for label in soup.find_all(string=re.compile(r"funder", re.I)):
        parent = label.parent
        sibling = parent.find_next_sibling()
        if sibling:
            return sibling.get_text(strip=True)
    return "UKRI"


async def _fetch_detail(
    client: httpx.AsyncClient,
    card_data: dict,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Fetch the detail page for one opportunity and merge its content."""
    async with semaphore:
        detail_url = card_data.get("url", "")
        if not detail_url:
            return card_data

        soup = await _fetch_html(client, detail_url, label=card_data.get("title", ""))
        if soup is None:
            return card_data

        # Description: prefer the main article / opportunity body
        description = ""
        for selector in [
            "article .opportunity-description",
            ".opportunity-body",
            "main article",
            ".wysiwyg-content",
            "main p",
        ]:
            el = soup.select_one(selector)
            if el:
                description = el.get_text(separator=" ", strip=True)
                break

        if not description:
            # Last resort: all paragraphs in main
            paras = soup.select("main p")
            description = " ".join(p.get_text(strip=True) for p in paras[:10])

        # Dates on detail page are more reliable
        open_text = close_text = None
        for el in soup.select(".opportunity-dates li, .meta-item, dl dt"):
            label = el.get_text(strip=True).lower()
            value_el = el.find_next_sibling() or el.parent.find("dd")
            value = value_el.get_text(strip=True) if value_el else ""
            if "open" in label or "opening" in label:
                open_text = value
            elif "clos" in label or "deadline" in label:
                close_text = value

        open_date = _parse_date(open_text) or card_data.get("open_date")
        close_date = _parse_date(close_text) or card_data.get("deadline")
        funder = _extract_funder(soup) or card_data.get("funder", "UKRI")

        # Total fund amount
        total_fund: float | None = card_data.get("funding_max")
        for el in soup.select(".opportunity-fund, .meta-item--budget, [data-fund]"):
            total_fund = _parse_gbp(el.get_text(strip=True)) or total_fund

        full_text = f"{card_data['title']} {description}"
        card_data.update(
            description=description or card_data.get("description"),
            summary=(description[:200] if description else card_data.get("summary")),
            open_date=open_date,
            deadline=close_date,
            status=_derive_status(open_date, close_date),
            funder=funder,
            funding_max=total_fund,
            eligibility_sectors=extract_sectors_from_text(full_text),
        )
        return card_data


def _parse_listing_card(card: BeautifulSoup, base_url: str) -> dict | None:
    """Parse a single opportunity card from the listing page."""
    try:
        title_el = card.select_one("h2 a, h3 a, .opportunity-title a, a.opportunity-link")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        url = href if href.startswith("http") else f"https://www.ukri.org{href}"

        summary = ""
        summary_el = card.select_one("p, .opportunity-summary")
        if summary_el:
            summary = summary_el.get_text(strip=True)

        funder = "UKRI"
        funder_el = card.select_one(".opportunity-funder, [data-funder]")
        if funder_el:
            funder = funder_el.get_text(strip=True)

        deadline_text = None
        date_el = card.select_one("time, .opportunity-deadline, [data-deadline]")
        if date_el:
            deadline_text = date_el.get("datetime") or date_el.get_text(strip=True)

        fund_text = None
        fund_el = card.select_one(".opportunity-fund, [data-fund]")
        if fund_el:
            fund_text = fund_el.get_text(strip=True)

        deadline = _parse_date(deadline_text)
        funding_max = _parse_gbp(fund_text)
        full_text = f"{title} {summary}"
        return dict(
            source="ukri_opportunity",
            external_id=_slugify(title),
            title=title[:500],
            description=summary or None,
            summary=summary[:200] if summary else None,
            funder=funder,
            programme="UKRI Opportunities",
            funding_min=None,
            funding_max=funding_max,
            open_date=None,
            deadline=deadline,
            status=_derive_status(None, deadline),
            eligibility_org_types=["sme", "startup", "university", "large_company"],
            eligibility_sectors=extract_sectors_from_text(full_text),
            eligibility_regions=["uk"],
            eligibility_trl=None,
            url=url,
        )
    except Exception as exc:
        logger.warning("Failed to parse UKRI opportunity card: %s", exc)
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


async def ingest_ukri_opportunities(db_session: AsyncSession) -> int:
    """
    Scrape the UKRI Opportunities listing and upsert Grant rows.

    Returns the total number of records processed.
    """
    settings = get_settings()
    listing_url = settings.ukri_opportunities_url
    total = 0
    semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "GrantMatch-Ingest/1.0 (research tool)"},
    ) as client:
        # Collect all pages of the listing
        page = 1
        all_cards: list[dict] = []
        while True:
            params = {"page": page} if page > 1 else {}
            soup = await _fetch_html(client, listing_url + ("" if not params else ""), label=f"listing page {page}")
            if soup is None:
                break

            cards = (
                soup.select("article.opportunity-card")
                or soup.select("li.opportunity")
                or soup.select(".opportunity-listing article")
                or soup.select("div.card")
            )
            if not cards:
                logger.info("UKRI Opportunities: no cards on page %d, stopping.", page)
                break

            for card in cards:
                data = _parse_listing_card(card, "https://www.ukri.org")
                if data:
                    all_cards.append(data)

            next_el = soup.select_one("a[rel='next'], .pagination__next a")
            if not next_el:
                break
            page += 1

        logger.info("UKRI Opportunities: found %d cards, fetching detail pages.", len(all_cards))

        # Fetch all detail pages concurrently (bounded by semaphore)
        tasks = [
            _fetch_detail(client, card, semaphore)
            for card in all_cards
        ]
        enriched = await asyncio.gather(*tasks)

        for data in enriched:
            await _upsert(db_session, data)
            total += 1

        await db_session.commit()

    logger.info("UKRI Opportunities ingestion complete: %d records total.", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    async def _main() -> None:
        await create_all_tables()
        async with AsyncSessionLocal() as session:
            count = await ingest_ukri_opportunities(session)
        print(f"Done — {count} UKRI Opportunity records upserted.")

    asyncio.run(_main())
