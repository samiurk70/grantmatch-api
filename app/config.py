from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///data/grants.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def coerce_db_url(cls, v: str) -> str:
        # Railway (and Heroku) provide postgres:// or postgresql:// —
        # asyncpg requires the +asyncpg dialect prefix.
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    embedding_model: str = "all-MiniLM-L6-v2"
    model_path: str = "ml/model.pkl"
    faiss_index_path: str = "data/grants.faiss"
    api_key: str = "changeme"
    max_results: int = 20
    gtr_api_base: str = "https://gtr.ukri.org/gtr/api"
    ukri_opportunities_url: str = "https://www.ukri.org/opportunity/"

    model_config = {"env_file": ".env", "protected_namespaces": ()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
