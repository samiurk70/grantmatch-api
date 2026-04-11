from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, Index, Integer, JSON, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Grant(Base):
    __tablename__ = "grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source metadata
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # Values: "ukri_gtr" | "cordis" | "govuk" | "ukri_opportunity"
    external_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)

    # Core content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(String(1000))
    funder: Mapped[Optional[str]] = mapped_column(String(200))
    programme: Mapped[Optional[str]] = mapped_column(String(200))

    # Financials (GBP equivalent)
    funding_min: Mapped[Optional[float]] = mapped_column(Float)
    funding_max: Mapped[Optional[float]] = mapped_column(Float)

    # Dates
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)
    open_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Status: "open" | "upcoming" | "closed"
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")

    # Eligibility criteria stored as JSON arrays.
    # Typed as Optional[Any] — SQLAlchemy 2.0 cannot introspect Optional[list[str]]
    # on Python 3.14 (Union.__getitem__ changed); runtime types enforced by Pydantic.
    eligibility_org_types: Mapped[Optional[Any]] = mapped_column(JSON)
    # e.g. ["sme", "university", "charity", "large_company", "individual"]

    eligibility_sectors: Mapped[Optional[Any]] = mapped_column(JSON)
    # e.g. ["ai", "healthcare", "clean_energy", "manufacturing", "net_zero"]

    eligibility_regions: Mapped[Optional[Any]] = mapped_column(JSON)
    # e.g. ["uk", "england", "eu", "international"]

    eligibility_trl: Mapped[Optional[Any]] = mapped_column(JSON)
    # e.g. [1, 4] means TRL 1–4 inclusive

    url: Mapped[Optional[str]] = mapped_column(String(500))

    # Embedding: serialised numpy float32 array (written by build_index.py)
    embedding_vector: Mapped[Optional[bytes]] = mapped_column(LargeBinary)

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_grants_source", "source"),
        Index("ix_grants_status", "status"),
        Index("ix_grants_deadline", "deadline"),
        Index("ix_grants_funder", "funder"),
    )

    def __repr__(self) -> str:
        return f"<Grant id={self.id} source={self.source!r} title={self.title[:40]!r}>"
