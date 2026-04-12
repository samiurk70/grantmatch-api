import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_all_tables
from app.api.routes import router
from app.services.embedder import get_embedder
from app.services.reranker import get_reranker
from app.services.matcher import get_matcher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Ensure DB tables exist
    await create_all_tables()

    # 2. Warm up ML singletons (blocks until model files are loaded)
    get_embedder()    # downloads model on first run (~90 MB, cached after)
    get_reranker()    # loads XGBoost model or logs heuristic fallback
    get_matcher()     # loads FAISS index or logs warning if absent

    logger.info("GrantMatch API ready.")
    yield


app = FastAPI(
    title="GrantMatch API",
    description="ML-scored grant matching for UK and EU funding opportunities.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow all origins for development — tighten in production via env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
async def health_simple():
    """Lightweight health check for Docker / load-balancer probes."""
    return {"status": "ok"}
