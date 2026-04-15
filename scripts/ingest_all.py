"""
Populate the database from all web-scrapable sources, build the FAISS index,
and train the XGBoost reranker — in one shot.

Usage (from project root):
    python -m scripts.ingest_all

Sources included (no manual downloads needed):
  - GOV.UK Find a Grant       ~101 records
  - UKRI Opportunities        ~111 records
  - UKRI Gateway to Research  ~5,000 records  (takes ~5 min — paginates API)

CORDIS (19,476 records) is NOT included — it requires a manual CSV download
from data.europa.eu. Run python -m data.ingest.ingest_cordis separately if
you have data/raw/project.csv.

After ingestion the script builds the FAISS index (all-MiniLM-L6-v2, ~20 min
on CPU) and trains the XGBoost reranker on synthetic pairs (~30 sec).

On Railway: use the one-off command feature or the shell tab to run this
after the first deploy so the Postgres database is populated.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import sys

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


def _run_build_index() -> None:
    logger.info("=== Building FAISS index ===")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.build_index"],
        check=False,
    )
    if result.returncode != 0:
        logger.error("build_index failed — FAISS index not created. Continuing.")
    else:
        logger.info("FAISS index built.")


def _run_train() -> None:
    logger.info("=== Training XGBoost reranker ===")
    result = subprocess.run(
        [sys.executable, "ml/train.py"],
        check=False,
    )
    if result.returncode != 0:
        logger.error("ml/train.py failed — model.pkl not created. Heuristic fallback will be used.")
    else:
        logger.info("XGBoost model trained and saved to ml/model.pkl.")


if __name__ == "__main__":
    asyncio.run(_run_ingestion())
    _run_build_index()
    _run_train()
    logger.info("=== ingest_all complete ===")
