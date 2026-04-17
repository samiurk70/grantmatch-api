"""
Build a FAISS IndexFlatIP from grant embeddings and persist it to disk.

Standalone usage:
    python -m scripts.build_index

What it does:
  1. Streams Grant rows that have a non-null description in batches of BATCH_SIZE
     (never loads all rows into RAM at once — safe on 1 GB Railway instances).
  2. Encodes  title + " " + description[:500]  with the sentence-transformer
     singleton (all-MiniLM-L6-v2 by default).
  3. Bulk-updates Grant.embedding_vector bytes to DB after each batch.
  4. Adds each batch's vectors to the FAISS index incrementally.
  5. Serialises the final index to FAISS_INDEX_PATH.

Run this script after any ingestion job that adds or updates grants.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import faiss
import numpy as np
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, create_all_tables
from app.models.db_models import Grant
from app.services.embedder import get_embedder

logger = logging.getLogger(__name__)

BATCH_SIZE = 128  # lower than the old 256 — safer on 1 GB RAM


def _text_for_row(id_: int, title: str, description: str | None) -> str:
    desc = (description or "")[:500]
    return f"{title} {desc}".strip()


def _pack_vector(vec: np.ndarray) -> bytes:
    """Serialise a float32 1-D numpy array to raw bytes."""
    return vec.astype(np.float32).tobytes()


async def build_index(db_session: AsyncSession) -> int:
    """
    Encode all grants with descriptions, store embeddings in DB, build
    and save a FAISS index.

    Memory strategy: loads BATCH_SIZE rows at a time using offset pagination,
    adds vectors to the FAISS index incrementally, and bulk-updates the DB
    after each batch.  Peak RAM ≈ model size (~100 MB) + one batch of text/
    vectors — well within a 1 GB container.

    Returns the number of vectors indexed.
    """
    settings = get_settings()
    index_path = Path(settings.faiss_index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    embedder = get_embedder()

    # ------------------------------------------------------------------ #
    # Determine embedding dimension from a dummy encode so we can build
    # the FAISS index before the first real batch arrives.
    # ------------------------------------------------------------------ #
    sample = embedder.encode(["dimension probe"])
    dim = sample.shape[1]

    base_index = faiss.IndexFlatIP(dim)
    id_index = faiss.IndexIDMap(base_index)

    # ------------------------------------------------------------------ #
    # Count total grants so we can log progress
    # ------------------------------------------------------------------ #
    from sqlalchemy import func
    count_result = await db_session.execute(
        select(func.count()).select_from(Grant).where(Grant.description.isnot(None))
    )
    total_grants = count_result.scalar_one() or 0
    if total_grants == 0:
        logger.warning("No grants with descriptions found — index not built.")
        return 0
    logger.info("Indexing %d grants with descriptions (batch size=%d).", total_grants, BATCH_SIZE)

    # ------------------------------------------------------------------ #
    # Offset-based batch loop — only BATCH_SIZE ORM rows in RAM at once.
    # Select only the three columns needed; skip heavy JSON fields.
    # ------------------------------------------------------------------ #
    total_indexed = 0
    offset = 0

    while True:
        result = await db_session.execute(
            select(Grant.id, Grant.title, Grant.description)
            .where(Grant.description.isnot(None))
            .order_by(Grant.id)
            .limit(BATCH_SIZE)
            .offset(offset)
        )
        rows = result.all()
        if not rows:
            break

        batch_ids = [r.id for r in rows]
        texts = [_text_for_row(r.id, r.title, r.description) for r in rows]

        # Encode — returns (batch, dim) float32, L2-normalised
        vectors: np.ndarray = embedder.encode(texts)

        # Bulk-update embedding_vector for this batch
        await db_session.execute(
            update(Grant),
            [
                {"id": gid, "embedding_vector": _pack_vector(vec)}
                for gid, vec in zip(batch_ids, vectors)
            ],
        )
        await db_session.commit()

        # Add this batch to the FAISS index
        ids_arr = np.array(batch_ids, dtype=np.int64)
        id_index.add_with_ids(vectors.astype(np.float32), ids_arr)

        total_indexed += len(rows)
        offset += BATCH_SIZE
        logger.info(
            "Encoded and indexed %d / %d grants.",
            total_indexed,
            total_grants,
        )

    if total_indexed == 0:
        logger.warning("No grants indexed — check that descriptions are present.")
        return 0

    faiss.write_index(id_index, str(index_path))
    logger.info(
        "Built FAISS index with %d vectors (dim=%d) → %s",
        id_index.ntotal,
        dim,
        index_path,
    )
    return id_index.ntotal


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    async def _main() -> None:
        await create_all_tables()
        async with AsyncSessionLocal() as session:
            n = await build_index(session)
        if n:
            print(f"Built FAISS index with {n} vectors.")
        else:
            print("No vectors indexed — run an ingestion script first.")
            sys.exit(1)

    asyncio.run(_main())
