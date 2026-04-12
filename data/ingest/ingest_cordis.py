"""
Ingest Horizon Europe project data from the CORDIS bulk CSV download.

Standalone usage:
    python -m data.ingest.ingest_cordis
    python -m data.ingest.ingest_cordis --csv /path/to/cordis.csv

The CSV is downloaded once to data/raw/cordis-HorizonEurope-projects.csv
if it doesn't already exist, then parsed with pandas.
UK still participates in Horizon Europe as an Associate Country.

Download URL (no auth required):
    https://cordis.europa.eu/data/cordis-HorizonEurope-projects.csv
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, create_all_tables
from app.models.db_models import Grant
from data.ingest import extract_sectors_from_text

logger = logging.getLogger(__name__)

CORDIS_CSV_URL = "https://cordis.europa.eu/data/cordis-HorizonEurope-projects.csv"
DEFAULT_CSV_PATH = Path("data/raw/cordis-HorizonEurope-projects.csv")
EUR_TO_GBP = 0.855  # approximate; update as needed
CHUNK_SIZE = 500     # rows between commits
REQUEST_TIMEOUT = 120.0


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

async def _download_csv(dest: Path) -> None:
    """Stream the CORDIS CSV to *dest*, creating parent dirs as needed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading CORDIS CSV → %s", dest)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        async with client.stream("GET", CORDIS_CSV_URL) as response:
            response.raise_for_status()
            with dest.open("wb") as fh:
                async for chunk in response.aiter_bytes(chunk_size=65_536):
                    fh.write(chunk)
    logger.info("Download complete: %s (%.1f MB)", dest, dest.stat().st_size / 1_048_576)


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

def _safe_str(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def _safe_float(value) -> float | None:
    try:
        f = float(value)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _parse_csv_date(value) -> datetime | None:
    text = _safe_str(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%SZ", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _derive_status(end_date: datetime | None) -> str:
    if end_date is None:
        return "open"
    return "closed" if end_date < datetime.utcnow() else "open"


def _build_grant(row: pd.Series) -> dict | None:
    """Map one CORDIS CSV row to Grant column kwargs. Returns None to skip."""
    external_id = _safe_str(row.get("id") or row.get("rcn"))
    if not external_id:
        return None

    title = _safe_str(row.get("title") or row.get("acronym"))
    if not title:
        return None

    description = _safe_str(row.get("objective") or row.get("description") or "")
    summary = description[:200] if description else ""

    ec_contrib = _safe_float(row.get("ecMaxContribution") or row.get("totalCost"))
    funding_max = round(ec_contrib * EUR_TO_GBP, 2) if ec_contrib else None

    start_date = _parse_csv_date(row.get("startDate"))
    end_date = _parse_csv_date(row.get("endDate"))
    status = _derive_status(end_date)

    # topics column is semicolon-separated topic codes, e.g. "HORIZON-CL4-2022-..."
    topics = _safe_str(row.get("topics") or "")
    text_for_sectors = f"{title} {description} {topics}"

    # legalBasis is usually the specific call, e.g. "HORIZON-RIA"
    programme_text = _safe_str(row.get("legalBasis") or row.get("frameworkProgramme") or "")

    return dict(
        source="cordis",
        external_id=external_id,
        title=title[:500],
        description=description or None,
        summary=summary or None,
        funder="European Commission",
        programme=f"Horizon Europe — {programme_text}" if programme_text else "Horizon Europe",
        funding_min=None,
        funding_max=funding_max,
        open_date=start_date,
        deadline=end_date,
        status=status,
        eligibility_org_types=["sme", "university", "large_company", "startup"],
        eligibility_sectors=extract_sectors_from_text(text_for_sectors),
        eligibility_regions=["eu", "uk"],
        eligibility_trl=None,
        url=f"https://cordis.europa.eu/project/id/{external_id}",
    )


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

async def ingest_cordis_csv(
    db_session: AsyncSession,
    csv_path: Path = DEFAULT_CSV_PATH,
    download_if_missing: bool = True,
) -> int:
    """
    Parse the CORDIS CSV at *csv_path* and upsert Grant rows.

    If the file doesn't exist and *download_if_missing* is True, it is
    downloaded first from cordis.europa.eu.

    Returns the total number of records processed.
    """
    if not csv_path.exists():
        if download_if_missing:
            await _download_csv(csv_path)
        else:
            raise FileNotFoundError(f"CORDIS CSV not found: {csv_path}")

    logger.info("Reading CORDIS CSV: %s", csv_path)
    # CORDIS CSVs use semicolon separators and may have a BOM
    try:
        df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig", low_memory=False)
    except Exception:
        df = pd.read_csv(csv_path, sep=",", encoding="utf-8-sig", low_memory=False)

    logger.info("CORDIS CSV loaded: %d rows, columns: %s", len(df), list(df.columns[:10]))

    total = 0
    skipped = 0

    for i, (_, row) in enumerate(df.iterrows()):
        data = _build_grant(row)
        if data is None:
            skipped += 1
            continue

        try:
            await _upsert(db_session, data)
            total += 1
        except Exception as exc:
            logger.warning("Skipping CORDIS row %d (id=%s): %s", i, row.get("id"), exc)
            skipped += 1

        if total % CHUNK_SIZE == 0 and total > 0:
            await db_session.commit()
            logger.info("CORDIS: upserted %d records (skipped %d).", total, skipped)

    await db_session.commit()
    logger.info(
        "CORDIS ingestion complete: %d records upserted, %d skipped.", total, skipped
    )
    return total


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest CORDIS Horizon Europe CSV")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"Path to CSV file (default: {DEFAULT_CSV_PATH}). "
             "Downloaded automatically if absent.",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Fail instead of downloading if CSV is missing.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    async def _main() -> None:
        await create_all_tables()
        async with AsyncSessionLocal() as session:
            count = await ingest_cordis_csv(
                session,
                csv_path=args.csv,
                download_if_missing=not args.no_download,
            )
        print(f"Done — {count} CORDIS records upserted.")

    asyncio.run(_main())
