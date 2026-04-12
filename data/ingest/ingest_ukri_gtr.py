"""
Ingest funded project data from the UKRI Gateway to Research (GtR) API.

Standalone usage:
    python -m data.ingest.ingest_ukri_gtr

The GtR API is public, paginated JSON, no authentication required.
We treat every funded project as a *closed* grant — historical signal
for what kinds of research UKRI funds, used to train the reranker.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, create_all_tables
from app.models.db_models import Grant
from data.ingest import extract_sectors_from_text

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
REQUEST_TIMEOUT = 30.0
RETRY_ATTEMPTS = 3


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _funding_pounds(project: dict) -> float | None:
    try:
        return float(project["fund"]["valuePounds"])
    except (KeyError, TypeError, ValueError):
        return None


def _programme(project: dict) -> str | None:
    # leadFunder is occasionally nested differently across GtR versions
    return (
        project.get("leadFunder")
        or project.get("fund", {}).get("funder", {}).get("name")
        or None
    )


def _build_grant(project: dict) -> dict:
    """Map a raw GtR project dict to Grant column kwargs."""
    description = project.get("abstractText") or ""
    summary = description[:200] if description else ""
    title = project.get("title") or ""
    text_for_sectors = f"{title} {description}"
    fund_start = _parse_date(project.get("fund", {}).get("start"))
    fund_end = _parse_date(project.get("fund", {}).get("end"))
    return dict(
        source="ukri_gtr",
        external_id=project["id"],
        title=title[:500],
        description=description or None,
        summary=summary or None,
        funder="UKRI",
        programme=_programme(project),
        funding_min=None,
        funding_max=_funding_pounds(project),
        open_date=fund_start,
        deadline=fund_end,
        status="closed",
        eligibility_org_types=["university", "sme", "large_company"],
        eligibility_regions=["uk"],
        eligibility_sectors=extract_sectors_from_text(text_for_sectors),
        eligibility_trl=None,
        url=f"https://gtr.ukri.org/projects?ref={project['id']}",
    )


async def _upsert(session: AsyncSession, data: dict) -> None:
    """Insert or update a Grant row, keyed on external_id."""
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


async def ingest_ukri_gtr(
    db_session: AsyncSession,
    max_pages: int = 50,
) -> int:
    """
    Paginate through the GtR /projects endpoint and upsert Grant rows.

    Returns the total number of records processed.
    """
    settings = get_settings()
    base_url = settings.gtr_api_base.rstrip("/")
    total = 0

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={"Accept": "application/vnd.rcuk.gtr.json-v7"},
        follow_redirects=True,
    ) as client:
        for page in range(1, max_pages + 1):
            params = {"p": page, "s": PAGE_SIZE}
            last_exc: Exception | None = None

            for attempt in range(1, RETRY_ATTEMPTS + 1):
                try:
                    response = await client.get(f"{base_url}/projects", params=params)
                    response.raise_for_status()
                    break
                except httpx.HTTPError as exc:
                    last_exc = exc
                    logger.warning(
                        "GtR page %d attempt %d/%d failed: %s",
                        page, attempt, RETRY_ATTEMPTS, exc,
                    )
                    await asyncio.sleep(2 ** attempt)
            else:
                logger.error("Giving up on GtR page %d after %d attempts: %s", page, RETRY_ATTEMPTS, last_exc)
                break

            payload = response.json()
            # GtR v7 wraps results under "project" or "projects"
            projects = (
                payload.get("project")
                or payload.get("projects")
                or []
            )

            if not projects:
                logger.info("GtR: no more projects on page %d, stopping.", page)
                break

            for project in projects:
                try:
                    await _upsert(db_session, _build_grant(project))
                    total += 1
                except Exception as exc:
                    logger.warning("Skipping GtR project %s: %s", project.get("id"), exc)

            await db_session.commit()

            if total % 500 == 0 and total > 0:
                logger.info("GtR: upserted %d records so far (page %d).", total, page)

            # Stop if last page returned fewer results than requested
            if len(projects) < PAGE_SIZE:
                break

    logger.info("GtR ingestion complete: %d records total.", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    async def _main() -> None:
        await create_all_tables()
        async with AsyncSessionLocal() as session:
            count = await ingest_ukri_gtr(session)
        print(f"Done — {count} UKRI GtR records upserted.")

    asyncio.run(_main())
