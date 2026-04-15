"""
Populate the database from all web-scrapable sources, build the FAISS index,
and train the XGBoost reranker — in one shot.

Usage (from project root):
    python -m scripts.ingest_all

Sources included (no manual downloads needed):
  - GOV.UK Find a Grant       ~107 records
  - UKRI Opportunities        ~114 records
  - UKRI Gateway to Research  ~5,000 records  (paginates API, takes ~5 min)

CORDIS (19,476 records) is NOT included — it requires a manual CSV download.
Run python -m data.ingest.ingest_cordis separately if you have data/raw/project.csv.

On Railway: use the Shell tab or a one-off command to run this after the first
deploy. The Postgres database persists across redeploys; FAISS and model.pkl
do not (ephemeral filesystem) — re-run just the index/train steps if needed.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import sys

# Silence httpx's per-request INFO logs — they flood the output.
# Errors and warnings from httpx are still shown.
logging.getLogger("httpx").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def _run_ingestion() -> None:
    from app.database import AsyncSessionLocal, create_all_tables
    from data.ingest.ingest_govuk_grants import ingest_govuk_grants
    from data.ingest.ingest_ukri_opportunities import ingest_ukri_opportunities
    from data.ingest.ingest_ukri_gtr import ingest_ukri_gtr

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
