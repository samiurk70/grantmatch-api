from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

_is_postgres = "postgresql" in settings.database_url

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,  # re-verify connections before use; handles Railway's idle-connection recycling
    **({
        "pool_size": 5,
        "max_overflow": 10,
    } if _is_postgres else {
        "connect_args": {"check_same_thread": False},
    }),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session and closes it after the request."""
    async with AsyncSessionLocal() as session:
        yield session


async def create_all_tables() -> None:
    """Create all ORM-mapped tables if they don't already exist."""
    # Import models so their metadata is registered on Base before create_all.
    import app.models.db_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
