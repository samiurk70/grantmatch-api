"""All API endpoints for GrantMatch."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.db_models import Grant
from app.models.schemas import (
    ApplicantProfile,
    GrantSummary,
    HealthResponse,
    MatchResponse,
)
from app.services.matcher import get_matcher, match_grants
from app.services.reranker import get_reranker

router = APIRouter()

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    if api_key != get_settings().api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


async def _data_freshness(db: AsyncSession) -> str:
    result = await db.execute(select(func.max(Grant.updated_at)))
    latest = result.scalar_one_or_none()
    if latest is None:
        return "no data"
    return latest.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@router.get("/")
async def root():
    return {
        "name": "GrantMatch API",
        "version": "0.1.0",
        "description": "ML-scored grant matching for UK and EU funding",
        "docs": "/docs",
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)):
    settings = get_settings()

    count_result = await db.execute(select(func.count()).select_from(Grant))
    grants_in_db = count_result.scalar_one_or_none() or 0

    freshness_result = await db.execute(select(func.max(Grant.updated_at)))
    latest = freshness_result.scalar_one_or_none()
    last_ingestion = latest.strftime("%Y-%m-%d") if latest else None

    index_built = Path(settings.faiss_index_path).exists()
    model_loaded = get_reranker().model is not None

    return HealthResponse(
        status="ok",
        model_loaded=model_loaded,
        grants_in_db=grants_in_db,
        index_built=index_built,
        last_ingestion=last_ingestion,
    )


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

@router.post("/match", response_model=MatchResponse)
async def match(
    profile: ApplicantProfile,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> MatchResponse:
    """Accept an applicant profile and return ML-ranked grant matches."""
    t0 = time.perf_counter()

    grants = await match_grants(profile, profile.top_n or 10, db)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    freshness = await _data_freshness(db)

    return MatchResponse(
        profile_summary=profile.description[:100],
        total_matched=len(grants),
        grants=grants,
        processing_time_ms=round(elapsed_ms, 1),
        data_freshness=freshness,
    )


# ---------------------------------------------------------------------------
# Grant browse
# ---------------------------------------------------------------------------

@router.get("/grants", response_model=list[GrantSummary])
async def list_grants(
    status: Literal["open", "upcoming", "closed", "all"] = Query(
        "open", description="Filter by grant status"
    ),
    funder: Optional[str] = Query(None, description="Filter by funder name (partial match)"),
    sector: Optional[str] = Query(None, description="Filter by sector tag"),
    limit: int = Query(20, ge=1, le=50, description="Number of results (max 50)"),
    offset: int = Query(0, ge=0, description="Number of results to skip (for pagination)"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> list[GrantSummary]:
    """Browse the grant database — useful for development and debugging."""
    q = select(Grant)

    if status != "all":
        q = q.where(Grant.status == status)
    if funder:
        q = q.where(Grant.funder.ilike(f"%{funder}%"))

    # Primary sort by deadline (soonest first, NULLs last); secondary sort by
    # id keeps the order fully deterministic when deadlines are equal or absent.
    q = q.order_by(Grant.deadline.asc().nulls_last(), Grant.id.asc()).limit(limit).offset(offset)

    result = await db.execute(q)
    grants = result.scalars().all()

    summaries: list[GrantSummary] = []
    for g in grants:
        # Optional sector filter (JSON contains check done in Python — DB-agnostic)
        if sector and (not g.eligibility_sectors or sector not in g.eligibility_sectors):
            continue
        summaries.append(GrantSummary(
            grant_id=g.id,
            title=g.title,
            funder=g.funder or "Unknown",
            programme=g.programme,
            summary=g.summary,
            status=g.status,
            funding_range=_format_funding_range(g),
            deadline=g.deadline,
            url=g.url,
            eligibility_regions=g.eligibility_regions,
            eligibility_sectors=g.eligibility_sectors,
        ))

    return summaries


@router.get("/grants/{grant_id}", response_model=GrantSummary)
async def get_grant(
    grant_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> GrantSummary:
    """Retrieve a single grant record by its database ID."""
    result = await db.execute(select(Grant).where(Grant.id == grant_id))
    grant = result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail=f"Grant {grant_id} not found")

    return GrantSummary(
        grant_id=grant.id,
        title=grant.title,
        funder=grant.funder or "Unknown",
        programme=grant.programme,
        summary=grant.summary,
        status=grant.status,
        funding_range=_format_funding_range(grant),
        deadline=grant.deadline,
        url=grant.url,
        eligibility_regions=grant.eligibility_regions,
        eligibility_sectors=grant.eligibility_sectors,
    )
