"""
Populate the database from all sources, build the FAISS index, and train the
XGBoost reranker — in one shot.

Usage (from project root):
    python -m scripts.ingest_all

Sources:
  - GOV.UK Find a Grant        ~107 records  (web scrape)
  - UKRI Opportunities         ~114 records  (web scrape)
  - UKRI Gateway to Research   ~5,000 records (API, ~5 min)
  - CORDIS Horizon Europe      ~19,500 records (auto-downloaded CSV, ~30 min)
    Skipped automatically if CORDIS records are already in the database.

On Railway: run via the Shell tab after the first deploy.
  - Postgres data persists across redeploys.
  - FAISS index and model.pkl do not (ephemeral filesystem).
  - To rebuild index/model after a redeploy without re-ingesting, run:
      python -m scripts.build_index
      python ml/train.py
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import sys

# Silence httpx's per-request INFO logs — they flood the output.
logging.getLogger("httpx").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def _run_ingestion() -> None:
    from sqlalchemy import func, select

    from app.database import AsyncSessionLocal, create_all_tables
    from app.models.db_models import Grant
    from data.ingest.ingest_govuk_grants import ingest_govuk_grants
    from data.ingest.ingest_ukri_opportunities import ingest_ukri_opportunities
    from data.ingest.ingest_ukri_gtr import ingest_ukri_gtr
    from data.ingest.ingest_cordis import ingest_cordis_csv

    await create_all_tables()

    async with AsyncSessionLocal() as session:
        logger.info("=== GOV.UK Find a Grant ===")
        n = await ingest_govuk_grants(session)
        logger.info("GOV.UK done: %d records", n)

    async with AsyncSessionLocal() as session:
        logger.info("=== UKRI Opportunities ===")
        n = await ingest_ukri_opportunities(session)
        logger.info("UKRI Opportunities done: %d records", n)

    async with AsyncSessionLocal() as session:
        logger.info("=== UKRI Gateway to Research ===")
        n = await ingest_ukri_gtr(session)
        logger.info("UKRI GtR done: %d records", n)

    async with AsyncSessionLocal() as session:
        logger.info("=== CORDIS Horizon Europe ===")
        # Check if CORDIS data is already loaded to avoid re-downloading
        # the ~250 MB CSV on every subsequent run.
        result = await session.execute(
            select(func.count()).select_from(Grant).where(Grant.source == "cordis")
        )
        existing = result.scalar_one()
        if existing > 0:
            logger.info(
                "CORDIS already in DB (%d records) — skipping download.", existing
            )
        else:
            logger.info(
                "No CORDIS records found — downloading zip from cordis.europa.eu."
            )
            try:
                n = await ingest_cordis_csv(session)
                logger.info("CORDIS done: %d records", n)
            except Exception as exc:
                logger.error(
                    "CORDIS ingestion failed (%s) — continuing without it. "
                    "Re-run python -m scripts.ingest_all to retry.",
                    exc,
                )


async def _run_build_index() -> None:
    from app.database import AsyncSessionLocal, create_all_tables
    from scripts.build_index import build_index

    logger.info("=== Building FAISS index ===")
    await create_all_tables()
    async with AsyncSessionLocal() as session:
        n = await build_index(session)
    if n:
        logger.info("FAISS index built: %d vectors.", n)
    else:
        logger.warning("No vectors indexed — check that ingestion ran first.")


def _run_train() -> None:
    logger.info("=== Training XGBoost reranker ===")
    result = subprocess.run([sys.executable, "ml/train.py"], check=False)
    if result.returncode != 0:
        logger.warning("ml/train.py failed — heuristic fallback will be used.")
    else:
        logger.info("XGBoost model saved to ml/model.pkl.")


async def _main() -> None:
    await _run_ingestion()
    await _run_build_index()
    _run_train()
    logger.info("=== ingest_all complete ===")


if __name__ == "__main__":
    asyncio.run(_main())
