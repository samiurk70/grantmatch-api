"""Sentence-transformer singleton — loaded once at startup, reused per request."""
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import get_settings


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


def embed(texts: list[str]) -> np.ndarray:
    """Return L2-normalised embeddings for a list of texts."""
    model = get_embedder()
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return vectors
