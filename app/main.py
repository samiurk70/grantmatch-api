from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import create_all_tables
from app.api.routes import router
from app.services.embedder import get_embedder


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()
    get_embedder()  # warm up the embedding model at startup
    yield


app = FastAPI(
    title="GrantMatch API",
    description="ML-scored grant matching for UK and EU funding opportunities.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
