"""
Build a FAISS IndexFlatIP from grant embeddings and persist it to disk.

Standalone usage:
    python -m scripts.build_index

What it does:
  1. Loads every Grant row that has a non-null description.
  2. Encodes  title + " " + description[:500]  with the sentence-transformer
     singleton (all-MiniLM-L6-v2 by default).
  3. Stores the resulting float32 bytes back into Grant.embedding_vector
     so the matcher can map FAISS result indices to DB rows.
  4. Builds a FAISS IndexFlatIP (inner-product, equivalent to cosine
     similarity when vectors are L2-normalised, as our embedder does).
  5. Serialises the index to FAISS_INDEX_PATH.

Run this script after any ingestion job that adds or updates grants.
"""
from __future__ import annotations

import asyncio
import logging
import struct
import sys
from pathlib import Path

import faiss
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, create_all_tables
from app.models.db_models import Grant
from app.services.embedder import embed

logger = logging.getLogger(__name__)

BATCH_SIZE = 256  # grants encoded per embed() call


def _text_for_grant(grant: Grant) -> str:
    desc = (grant.description or "")[:500]
    return f"{grant.title} {desc}".strip()


def _pack_vector(vec: np.ndarray) -> bytes:
    """Serialise a float32 1-D numpy array to raw bytes."""
    return vec.astype(np.float32).tobytes()


def _unpack_vector(data: bytes) -> np.ndarray:
    n = len(data) // 4
    return np.frombuffer(data, dtype=np.float32).reshape(1, n)


async def build_index(db_session: AsyncSession) -> int:
    """
    Encode all grants with descriptions, store embeddings in DB, build
    and save a FAISS index.

    Returns the number of vectors indexed.
    """
    settings = get_settings()
    index_path = Path(settings.faiss_index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Load grants
    # ------------------------------------------------------------------ #
    result = await db_session.execute(
        select(Grant).where(Grant.description.isnot(None))
    )
    grants: list[Grant] = list(result.scalars().all())

    if not grants:
        logger.warning("No grants with descriptions found — index not built.")
        return 0

    logger.info("Loaded %d grants with descriptions.", len(grants))

    # ------------------------------------------------------------------ #
    # Encode in batches
    # ------------------------------------------------------------------ #
    all_vectors: list[np.ndarray] = []

    for batch_start in range(0, len(grants), BATCH_SIZE):
        batch = grants[batch_start : batch_start + BATCH_SIZE]
        texts = [_text_for_grant(g) for g in batch]
        vectors = embed(texts)  # shape (batch, dim), already L2-normalised

        for grant, vec in zip(batch, vectors):
            grant.embedding_vector = _pack_vector(vec)

        all_vectors.append(vectors)
        logger.info(
            "Encoded batch %d–%d / %d",
            batch_start + 1,
            min(batch_start + BATCH_SIZE, len(grants)),
            len(grants),
        )

    await db_session.commit()
    logger.info("Embedding vectors written to database.")

    # ------------------------------------------------------------------ #
    # Build FAISS index
    # ------------------------------------------------------------------ #
    matrix = np.vstack(all_vectors).astype(np.float32)
    dim = matrix.shape[1]

    index = faiss.IndexFlatIP(dim)  # inner product ≡ cosine on unit vectors
    # Wrap with IDMap so we can store Grant.id as the FAISS vector ID,
    # making retrieval → DB lookup a direct integer lookup.
    id_index = faiss.IndexIDMap(index)

    ids = np.array([g.id for g in grants], dtype=np.int64)
    id_index.add_with_ids(matrix, ids)

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
