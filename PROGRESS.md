# GrantMatch API — Session Progress Backup

## Status
Phase 3 complete. 6/6 tests passing.

## Environment
- Python 3.14.3 on Windows
- greenlet==3.4.0 manually added to requirements.txt (SQLAlchemy async dep)
- HF_HUB_DISABLE_SYMLINKS_WARNING should be set on Windows
- sentence-transformers model: all-MiniLM-L6-v2 (cached after first run)
- Docker not used for dev — run with: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

## Completed Phases

### Phase 1 — Project skeleton
All 16 source files created and syntax-verified. Dockerfile and 
docker-compose.yml created but Docker not used for local dev.

### Phase 2 — Database models and schemas
- app/models/db_models.py: Grant ORM model, 21 columns, 4 indexes
- app/models/schemas.py: ApplicantProfile (Literal types for 
  organisation_type and location, sectors validated against allowlist,
  description min 50 chars), GrantMatch (exactly 3 top_factors), 
  MatchResponse, HealthResponse, ErrorResponse
- app/database.py: async SQLAlchemy engine, get_db() dependency,
  create_all_tables(), connect_args check_same_thread for SQLite
- JSON columns typed as Mapped[Optional[Any]] due to Python 3.14 
  SQLAlchemy Union.__getitem__ bug
- routes.py takes ApplicantProfile directly, no MatchRequest wrapper

### Phase 3 — Data ingestion scripts
- data/ingest/__init__.py: extract_sectors_from_text() with 16 compiled 
  regex patterns covering all 19 sector tags
- data/ingest/ingest_ukri_gtr.py: paginates GtR API, Accept header 
  vnd.rcuk.gtr.json-v7, handles project/projects key variance, 
  exponential backoff retry, commits per page
- data/ingest/ingest_govuk_grants.py: scrapes find-government-grants
  .service.gov.uk, slugified external_id, status from deadline vs utcnow
- data/ingest/ingest_ukri_opportunities.py: two-phase scrape with 
  asyncio.Semaphore(5) for concurrent detail fetches, _parse_gbp handles
  million/k/m suffixes
- data/ingest/ingest_cordis.py: downloads CSV to data/raw/, handles ; 
  and , separators and UTF-8 BOM, EUR_TO_GBP=0.855, commits every 500 rows
- scripts/build_index.py: faiss.IndexIDMap wrapping IndexFlatIP, IDs are
  Grant.id integers, encodes in batches of 256, writes embedding_vector 
  bytes to DB before saving index

## Key Architecture Decisions
- SQLite for dev (DATABASE_URL=sqlite+aiosqlite:///data/grants.db)
- PostgreSQL swap = one env var change
- FAISS IndexIDMap — Grant.id integers map directly to DB rows
- All ingestion scripts runnable standalone as python -m data.ingest.X
- Heuristic scorer used until ml/model.pkl exists
- matcher.py currently raises NotImplementedError (Phase 4 implements it)
- reranker.py currently raises NotImplementedError (Phase 4 implements it)

## Next: Phase 4
Implement:
- app/services/embedder.py: SentenceEmbedder singleton
- app/services/matcher.py: full GrantMatcher with FAISS retrieval,
  eligibility filter, reranker scoring
- app/services/reranker.py: XGBoost model loader with heuristic fallback
- app/api/routes.py: full endpoints including /v1/grants browse and 
  /v1/grants/{id} detail
- app/utils/eligibility.py: check_eligibility returning verdict + factors
- app/utils/feature_extractor.py: 9-feature vector

## File Structure (complete)
grantmatch-api/
├── app/main.py, config.py, database.py
├── app/models/db_models.py, schemas.py
├── app/services/embedder.py, matcher.py, reranker.py
├── app/api/routes.py
├── app/utils/eligibility.py, feature_extractor.py
├── data/ingest/__init__.py + 4 ingest scripts
├── scripts/build_index.py
├── ml/train.py, evaluate.py
├── tests/test_api.py, test_matcher.py
└── CLAUDE.md, PROGRESS.md, requirements.txt, .env
