# GrantMatch API — Session Progress Backup

## Status
Phase 4 complete. 25/25 tests passing.

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
- matcher.py: full 8-step pipeline implemented (Phase 4)
- reranker.py: heuristic fallback active, XGBoost loads when model.pkl exists

## Phase 4 Complete
25/25 tests passing.

Implemented:
- app/utils/eligibility.py: check_eligibility() returns str verdict,
  _location_compatible() handles UK/sub-region bidirectional matching
- app/utils/feature_extractor.py: extract_features() returns dict[str,float],
  FEATURE_NAMES module constant, features_to_array() for model input
- app/services/embedder.py: SentenceEmbedder class, get_embedder() singleton
- app/services/reranker.py: GrantReranker class, joblib model load,
  heuristic weights sum to 100, _top3_factors() always returns exactly 3
- app/services/matcher.py: full 8-step pipeline, IndexIDMap FAISS,
  DB fallback when index absent
- app/models/schemas.py: added GrantSummary for browse endpoints
- app/api/routes.py: GET /api/v1/, GET /api/v1/health, GET /api/v1/grants,
  GET /api/v1/grants/{id}, POST /api/v1/match all implemented
- app/main.py: startup order embedder → reranker → matcher, CORS added,
  /health at root for Docker probes

## Next: Phase 5
- ml/train.py: XGBoost XGBClassifier, 1500 synthetic pairs, 4 label classes
- ml/evaluate.py: ndcg_at_k, mean_reciprocal_rank functions
- Full test suite expansion (test_api.py and test_matcher.py already done)
- README.md final version

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
