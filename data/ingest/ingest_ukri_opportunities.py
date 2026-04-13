"""
Ingest live Innovate UK / UKRI competitions from the UKRI Opportunities page.

Standalone usage:
    python -m data.ingest.ingest_ukri_opportunities

Card structure (WordPress, server-side rendered):
  div.opportunity  — one card per opportunity
    h3.entry-title > a.ukri-funding-opp__link  — title + detail URL
    div.entry-content > p                       — short summary
    dl.opportunity__summary  — metadata table:
      dt "Opportunity status:" → dd > span  (text: Open/Upcoming/Closed)
      dt "Funders:"            → dd > a.ukri-funder__link
      dt "Total fund:"         → dd
      dt "Opening date:"       → dd > time[datetime]
      dt "Closing date:"       → dd > time[datetime]

Pagination: a.next.page-numbers → href = .../opportunity/page/N/
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup, Tag
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, create_all_tables
from app.models.db_models import Grant
from data.ingest import extract_sectors_from_text

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30.0
RETRY_ATTEMPTS = 3
DETAIL_CONCURRENCY = 5  # concurrent detail-page fetches


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:190]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    # ISO datetime from the <time datetime="..."> attribute
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    # Human-readable formats from the text content
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(re.sub(r"\s+", " ", value.split(" UK")[0].strip()), fmt)
        except ValueError:
            continue
    return None


def _parse_gbp(text: str | None) -> float | None:
    """Extract a numeric GBP amount from strings like '£2.5 million' or '£500,000'."""
    if not text:
        return None
    text = text.replace(",", "").lower()
    match = re.search(r"£\s*([\d.]+)\s*(b(?:illion)?|m(?:illion)?|k)?", text)
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


def _dl_value(dl: Tag, label_text: str) -> Tag | None:
    """
    Find the <dd> that follows the <dt> whose text contains label_text
    (case-insensitive) inside a dl.
    """
    for row in dl.select("div.govuk-table__row"):
        dt = row.select_one("dt")
        dd = row.select_one("dd")
        if dt and dd and label_text.lower() in dt.get_text(strip=True).lower():
            return dd
    return None


def _derive_status(
    status_text: str | None,
    open_date: datetime | None,
    close_date: datetime | None,
) -> str:
    """Prefer the explicit status span; fall back to date-based derivation."""
    if status_text:
        s = status_text.strip().lower()
        if s in ("open", "upcoming", "closed"):
            return s
    now = datetime.utcnow()
    if close_date and close_date < now:
        return "closed"
    if open_date and open_date > now:
        return "upcoming"
    return "open"


def _parse_listing_card(card: Tag) -> dict | None:
    """Extract all available fields from a single opportunity listing card."""
    try:
        title_el = card.select_one("a.ukri-funding-opp__link")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")
        if url and not url.startswith("http"):
            url = f"https://www.ukri.org{url}"

        summary = ""
        summary_el = card.select_one("div.entry-content p")
        if summary_el:
            summary = summary_el.get_text(strip=True)

        # Metadata table
        dl = card.select_one("dl.opportunity__summary")
        status_text = funder = fund_text = None
        open_date = close_date = None

        if dl:
            # Status
            status_dd = _dl_value(dl, "Opportunity status")
            if status_dd:
                span = status_dd.select_one("span")
                status_text = span.get_text(strip=True) if span else status_dd.get_text(strip=True)

            # Funder
            funder_dd = _dl_value(dl, "Funders")
            if funder_dd:
                funder_a = funder_dd.select_one("a.ukri-funder__link")
                funder = (funder_a or funder_dd).get_text(strip=True)

            # Total fund
            fund_dd = _dl_value(dl, "Total fund")
            if fund_dd:
                fund_text = fund_dd.get_text(strip=True)

            # Opening date
            open_dd = _dl_value(dl, "Opening date")
            if open_dd:
                t = open_dd.select_one("time")
                open_date = _parse_date(
                    (t.get("datetime") if t else None) or open_dd.get_text(strip=True)
                )

            # Closing date
            close_dd = _dl_value(dl, "Closing date")
            if close_dd:
                t = close_dd.select_one("time")
                close_date = _parse_date(
                    (t.get("datetime") if t else None) or close_dd.get_text(strip=True)
                )

        funding_max = _parse_gbp(fund_text)
        status = _derive_status(status_text, open_date, close_date)
        full_text = f"{title} {summary}"

        return dict(
            source="ukri_opportunity",
            external_id=_slugify(title),
            title=title[:500],
            description=summary or None,
            summary=summary[:200] if summary else None,
            funder=funder or "UKRI",
            programme="UKRI Opportunities",
            funding_min=None,
            funding_max=funding_max,
            open_date=open_date,
            deadline=close_date,
            status=status,
            eligibility_org_types=["sme", "startup", "university", "large_company"],
            eligibility_sectors=extract_sectors_from_text(full_text),
            eligibility_regions=["uk"],
            eligibility_trl=None,
            url=url,
        )
    except Exception as exc:
        logger.warning("Failed to parse UKRI opportunity card: %s", exc)
        return None


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
            logger.warning(
                "Fetch %s attempt %d/%d failed: %s",
                label or url, attempt, RETRY_ATTEMPTS, exc,
            )
            await asyncio.sleep(2 ** attempt)
    logger.error("Giving up on %s: %s", label or url, last_exc)
    return None


async def _enrich_from_detail(
    client: httpx.AsyncClient,
    card_data: dict,
    semaphore: asyncio.Semaphore,
) -> dict:
    """
    Fetch the detail page to get the full description text.
    Other metadata (dates, funder, fund) is already extracted from the
    listing card and is not overwritten here.
    """
    async with semaphore:
        detail_url = card_data.get("url", "")
        if not detail_url:
            return card_data

        soup = await _fetch_html(
            client, detail_url, label=card_data.get("title", "")
        )
        if soup is None:
            return card_data

        # Try selectors for the full description on the detail page
        description = ""
        for selector in [
            ".wysiwyg-content",
            ".entry-content",
            "main article",
            "article .opportunity-description",
        ]:
            el = soup.select_one(selector)
            if el:
                description = el.get_text(separator=" ", strip=True)
                if len(description) > 100:
                    break

        if not description:
            paras = soup.select("main p")
            description = " ".join(p.get_text(strip=True) for p in paras[:10])

        if description and len(description) > len(card_data.get("description") or ""):
            full_text = f"{card_data['title']} {description}"
            card_data.update(
                description=description,
                summary=description[:200],
                eligibility_sectors=extract_sectors_from_text(full_text),
            )

        return card_data


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
    semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)
    total = 0

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "GrantMatch-Ingest/1.0 (research tool)"},
    ) as client:
        # Collect all pages of the listing
        current_url: str | None = listing_url
        page = 1
        all_cards: list[dict] = []

        while current_url:
            soup = await _fetch_html(client, current_url, label=f"listing page {page}")
            if soup is None:
                break

            # Each opportunity is a <div class="... opportunity ...">
            cards = soup.find_all("div", class_="opportunity")
            if not cards:
                logger.info("UKRI Opportunities: no cards on page %d, stopping.", page)
                break

            for card in cards:
                data = _parse_listing_card(card)
                if data:
                    all_cards.append(data)

            logger.info(
                "UKRI Opportunities: page %d — %d cards found (total so far: %d).",
                page, len(cards), len(all_cards),
            )

            # Follow the "Next" pagination link
            next_el = soup.select_one("a.next.page-numbers")
            current_url = next_el["href"] if next_el else None
            page += 1

        logger.info(
            "UKRI Opportunities: %d listing cards found, enriching from detail pages.",
            len(all_cards),
        )

        # Enrich with detail-page descriptions (bounded concurrency)
        tasks = [_enrich_from_detail(client, card, semaphore) for card in all_cards]
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
