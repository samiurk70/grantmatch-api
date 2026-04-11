from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Grant(Base):
    __tablename__ = "grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(50))          # ukri_gtr | cordis | govuk | ukri_opp
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[Optional[str]] = mapped_column(Text)
    funder: Mapped[Optional[str]] = mapped_column(String(255))
    max_award_gbp: Mapped[Optional[float]] = mapped_column(Float)
    deadline: Mapped[Optional[date]] = mapped_column(Date)
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    eligibility_notes: Mapped[Optional[str]] = mapped_column(Text)
    trl_min: Mapped[Optional[int]] = mapped_column(Integer)   # technology readiness level
    trl_max: Mapped[Optional[int]] = mapped_column(Integer)
    sector_tags: Mapped[Optional[str]] = mapped_column(Text)  # comma-separated
    region: Mapped[Optional[str]] = mapped_column(String(50)) # UK | EU | both
    embedding_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)  # FAISS row index
