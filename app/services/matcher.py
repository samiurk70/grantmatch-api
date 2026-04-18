"""Core matching pipeline: embed → FAISS retrieval → eligibility filter → rerank."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.db_models import Grant
from app.models.schemas import ApplicantProfile, GrantMatch, MatchResponse
from app.services.embedder import SentenceEmbedder, get_embedder
from app.services.reranker import GrantReranker, get_reranker
from app.utils.eligibility import check_eligibility
from app.utils.feature_extractor import extract_features

logger = logging.getLogger(__name__)

_CANDIDATE_POOL = 150  # top-K from FAISS before reranking (wider pool → more score variance)
_FALLBACK_POOL  = 50   # random grants when FAISS unavailable


def _format_funding_range(grant: Grant) -> str:
    def _fmt(v: float) -> str:
        if v >= 1_000_000:
            return f"£{v / 1_000_000:.1f}m"
        if v >= 1_000:
            return f"£{v / 1_000:.0f}k"
        return f"£{v:.0f}"

    lo, hi = grant.funding_min, grant.funding_max
    if lo and hi:
        return f"{_fmt(lo)} – {_fmt(hi)}"
    if hi:
        return f"Up to {_fmt(hi)}"
    if lo:
        return f"From {_fmt(lo)}"
    return "Unknown"


def _build_grant_match(
    grant: Grant,
    score: float,
    verdict: str,
    factors,
) -> GrantMatch:
    summary = grant.summary or (grant.description[:200] if grant.description else "")
    return GrantMatch(
        grant_id=grant.id,
        title=grant.title,
        funder=grant.funder or "Unknown",
        programme=grant.programme,
        summary=summary,
        score=round(score, 2),
        confidence=round(min(score / 100.0, 1.0), 4),
        deadline=grant.deadline,
        status=grant.status,
        funding_range=_format_funding_range(grant),
        eligibility_verdict=verdict,
        top_factors=factors[:3],
        url=grant.url,
    )


class GrantMatcher:
    """
    End-to-end matching pipeline.

    Holds references to the embedder, FAISS index, and reranker so they are
    loaded once and reused across requests.
    """

    def __init__(
        self,
        embedder: SentenceEmbedder | None = None,
        reranker: GrantReranker | None = None,
    ) -> None:
        self.embedder = embedder or get_embedder()
        self.reranker = reranker or get_reranker()
        self.index = None
        self._load_index()

    def _load_index(self) -> None:
        settings = get_settings()
        path = Path(settings.faiss_index_path)
        if not path.exists():
            logger.warning(
                "FAISS index not found at %s — semantic search disabled. "
                "Run scripts/build_index.py after ingestion.",
                path,
            )
            return
        try:
            import faiss
            self.index = faiss.read_index(str(path))
            logger.info("FAISS index loaded: %d vectors.", self.index.ntotal)
        except Exception as exc:
            logger.error("Failed to load FAISS index: %s", exc)

    async def match(
        self,
        profile: ApplicantProfile,
        db_session: AsyncSession,
    ) -> list[GrantMatch]:
        """
        Full matching pipeline.  Steps:
          1. Build query text from profile description + sectors
          2. Encode query with sentence-transformer
          3. Retrieve top-50 candidates (FAISS or DB fallback)
          4. Load Grant rows for candidates
          5. Eligibility filter — drop "likely_ineligible"
          6. Score each candidate with the reranker
          7. Sort descending, take top_n
          8. Build GrantMatch list
        """
        top_n = profile.top_n or 10

        # Step 1 & 2 — encode
        query_text = profile.description + " " + " ".join(profile.sectors)
        query_vec = self.embedder.encode_single(query_text).reshape(1, -1).astype(np.float32)

        # Step 3 — candidate retrieval
        if self.index is not None:
            candidate_ids, semantic_scores = self._faiss_search(query_vec)
        else:
            candidate_ids, semantic_scores = await self._db_fallback(db_session)

        if not candidate_ids:
            return []

        # Step 4 — load Grant rows
        result = await db_session.execute(
            select(Grant).where(Grant.id.in_(candidate_ids))
        )
        grants_by_id: dict[int, Grant] = {g.id: g for g in result.scalars().all()}

        # Step 5 — eligibility filter
        eligible: list[tuple[Grant, float, str]] = []
        for gid in candidate_ids:
            grant = grants_by_id.get(gid)
            if grant is None:
                continue
            verdict = check_eligibility(grant, profile)
            if verdict != "likely_ineligible":
                eligible.append((grant, semantic_scores.get(gid, 0.0), verdict))

        if not eligible:
            return []

        # Step 6 — rerank
        scored: list[tuple[Grant, float, str, list]] = []
        for grant, sem_score, verdict in eligible:
            features = extract_features(grant, profile, sem_score)
            score, factors = self.reranker.score(grant, profile, sem_score, features)
            scored.append((grant, score, verdict, factors))

        # Step 7 — sort and slice
        scored.sort(key=lambda t: t[1], reverse=True)
        top = scored[:top_n]

        # Step 8 — build response objects
        return [_build_grant_match(g, s, v, f) for g, s, v, f in top]

    def _faiss_search(
        self, query_vec: np.ndarray
    ) -> tuple[list[int], dict[int, float]]:
        distances, ids = self.index.search(query_vec, _CANDIDATE_POOL)
        candidate_ids: list[int] = []
        raw: dict[int, float] = {}
        for dist, gid in zip(distances[0], ids[0]):
            if gid == -1:   # FAISS padding for short indexes
                continue
            candidate_ids.append(int(gid))
            raw[int(gid)] = float(max(0.0, dist))

        # Min-max normalise across the pool so scores span [0.05, 1.0].
        # Raw inner-product scores from the top-150 cluster tightly (e.g. 0.40–0.49),
        # which collapses score variance in the reranker. Spreading them out preserves
        # relative ordering while giving the heuristic meaningful discrimination.
        scores: dict[int, float] = {}
        if raw:
            lo = min(raw.values())
            hi = max(raw.values())
            spread = hi - lo if hi > lo else 1.0
            scores = {gid: 0.05 + 0.95 * (v - lo) / spread for gid, v in raw.items()}
        return candidate_ids, scores

    async def _db_fallback(
        self, db_session: AsyncSession
    ) -> tuple[list[int], dict[int, float]]:
        """Return random open grants when the FAISS index is not available."""
        result = await db_session.execute(
            select(Grant)
            .where(Grant.status.in_(["open", "upcoming"]))
            .order_by(func.random())
            .limit(_FALLBACK_POOL)
        )
        grants = result.scalars().all()
        candidate_ids = [g.id for g in grants]
        scores = {g.id: 0.5 for g in grants}   # neutral score for fallback
        return candidate_ids, scores


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_matcher: GrantMatcher | None = None


def get_matcher() -> GrantMatcher:
    global _matcher
    if _matcher is None:
        _matcher = GrantMatcher()
    return _matcher


# ---------------------------------------------------------------------------
# Backward-compatible top-level function (used by tests and routes)
# ---------------------------------------------------------------------------

async def match_grants(profile: ApplicantProfile, top_k: int, db_session: AsyncSession) -> list[GrantMatch]:
    """Thin wrapper around GrantMatcher.match()."""
    profile_copy = profile.model_copy(update={"top_n": top_k})
    return await get_matcher().match(profile_copy, db_session)
