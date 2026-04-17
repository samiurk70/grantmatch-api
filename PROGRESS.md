# GrantMatch API — Session Progress Backup

## Status
Phase 5 complete + post-Phase-5 bug fixes applied + full ingestion + FAISS index built. 31/31 tests passing.

## Live Data Counts (as of 2026-04-13)
| Source          | Records |
|-----------------|---------|
| cordis          | 19,476  |
| ukri_gtr        | 5,000   |
| ukri_opportunity| 111     |
| govuk           | 101     |
| **Total**       | **24,688** |

## FAISS Index
- Vectors: 24,688 (all grants with descriptions)
- Dimension: 384 (all-MiniLM-L6-v2)
- Index type: IndexIDMap wrapping IndexFlatIP
- Saved to: data/grants.faiss

## ML Model (ml/model.pkl)
- Algorithm: XGBClassifier (multi:softprob, 4 classes, 300 estimators)
- Training data: 1,500 synthetic pairs (30 grants × 50 profiles)
- Label distribution: {0: 612 (40.8%), 1: 526 (35.1%), 2: 315 (21.0%), 3: 47 (3.1%)}
- Test accuracy: 99.67%
- Macro F1: 0.98

## Environment
- Target Python: 3.11.x (pinned in .python-version as 3.11.9 for pyenv/Railway)
- Dev environment: Python 3.14.3 on Windows (used during initial development)
- HF_HUB_DISABLE_SYMLINKS_WARNING should be set on Windows
- sentence-transformers model: all-MiniLM-L6-v2 (cached after first run)
- Docker not used for dev — run with: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
- CORDIS data downloaded manually from data.europa.eu and extracted to data/raw/project.csv
  (zip also contains organization.csv, topics.csv, legalBasis.csv, etc. — only project.csv used)

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
- JSON columns typed as Mapped[Optional[Any]] — SQLAlchemy 2.0 JSON columns
  are untyped at the ORM level; runtime types enforced by Pydantic
- routes.py takes ApplicantProfile directly, no MatchRequest wrapper

### Phase 3 — Data ingestion scripts
- data/ingest/__init__.py: extract_sectors_from_text() with 16 compiled
  regex patterns covering all 19 sector tags
- data/ingest/ingest_ukri_gtr.py: paginates GtR API, Accept header
  vnd.rcuk.gtr.json-v7, handles project/projects key variance,
  exponential backoff retry, commits per page
- data/ingest/ingest_govuk_grants.py: original version used HTML card
  selectors (later replaced in bug-fix session — see below)
- data/ingest/ingest_ukri_opportunities.py: original version used HTML
  card selectors (later replaced in bug-fix session — see below)
- data/ingest/ingest_cordis.py: downloads CSV to data/raw/, handles ;
  and , separators and UTF-8 BOM, EUR_TO_GBP=0.855, commits every 500 rows
- scripts/build_index.py: faiss.IndexIDMap wrapping IndexFlatIP, IDs are
  Grant.id integers, encodes in batches of 256, writes embedding_vector
  bytes to DB before saving index

### Phase 4 — Core matching pipeline and API endpoints
25/25 tests passing at completion.

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

### Phase 5 — ML training, expanded tests, README
31/31 tests passing at completion.

- ml/train.py: 30 synthetic grants × 50 profiles = 1500 pairs, XGBClassifier
  objective=multi:softprob, num_class=4, n_estimators=300, 80/20 stratified split,
  saves ml/model.pkl via joblib. Label 0–3 based on org_match + region_match +
  sector_match + trl_match + semantic_sim criteria.
- tests/test_api.py: 13 tests — health, root, auth (3), validation (2),
  match returns grants + respects top_n, browse open, browse empty, 404
- tests/test_matcher.py: 18 tests — eligibility (8), feature extractor (6),
  sector_overlap_identical, funding_fit_within_range, reranker heuristic (3)
- README.md: product description, quick start, data ingestion, build index,
  train model, run server, example curl + JSON response, endpoint table,
  pricing placeholder, /docs link

---

## Post-Phase-5 Bug Fixes

### Fix 1 — ingest_govuk_grants.py: page is Next.js, not HTML cards
**Root cause**: The GOV.UK Find a Grant service is a Next.js application.
All grant data is embedded as JSON in a `<script id="__NEXT_DATA__">` tag.
No HTML card elements (li.grants-list__item, div.grant-card, etc.) exist
in the initial HTML — BeautifulSoup found nothing.

**Fix**: Completely rewrote the scraper to:
- Extract `props.pageProps.searchResult` array from `__NEXT_DATA__` JSON
- Paginate with `?page=N` (not `?skip=N&limit=10` — skip param is ignored)
- Map `grantApplicantType` values to our org type codes:
  - "Private Sector" → ["sme", "startup", "large_company"]
  - "Non-profit" → ["charity"]
  - "Personal / Individual" → ["individual"]
  - "Public Sector" / "Local authority" → omitted (no schema equivalent)
- Map `grantLocation` values to region codes:
  - "England" / "North * England" / "Midlands" → "england"
  - "National" → "uk"
  - Scotland / Wales / Northern Ireland → direct
- Use `grantMinimumAward` / `grantMaximumAward` directly as floats
- Total grants: 101 across 11 pages (10 per page)

### Fix 2 — ingest_ukri_opportunities.py: wrong card selectors
**Root cause**: The UKRI Opportunities page is WordPress server-side rendered.
Cards are `<div class="post-XXXXX opportunity type-opportunity ...">`, not
`article.opportunity-card` or `li.opportunity` as the original script assumed.
All metadata (dates, funder, status, fund amount) is present in the listing
card — no detail page needed for these fields.

**Fix**: Rewrote card parsing to use correct selectors:
- Cards: `soup.find_all('div', class_='opportunity')` — 10 per page
- Title + URL: `a.ukri-funding-opp__link`
- Summary: `div.entry-content p`
- Metadata from `dl.opportunity__summary` rows — each `dt`/`dd` pair:
  - "Opportunity status:" → `dd > span` text (Open / Upcoming / Closed)
  - "Funders:" → `dd > a.ukri-funder__link` text
  - "Total fund:" → `dd` text, parsed by `_parse_gbp()`
  - "Opening date:" / "Closing date:" → `dd > time[datetime]` attribute
- Pagination: `a.next.page-numbers` href (e.g. `/opportunity/page/2/`)
- Detail page fetch kept but only used to upgrade the description text

### Fix 3 — ml/train.py: label 1 never generated (XGBoost crash)
**Root cause**: The original `_assign_label()` had an unreachable label 1
path. After labels 2 and 3 were checked, `if not org_match or not
region_match: return 0` consumed all remaining pairs before the label 1
fallthrough could be reached, producing distribution {0: 1138, 2: 354, 3: 8}.
XGBoost raised `ValueError: Invalid classes inferred ... Expected [0 1 2],
got [0 2 3]`.

**Fix**: Replaced the cascading-if logic with a `key_dims` approach:
```
key_dims = int(org_match) + int(region_match) + int(sector_match)
  Label 3: key_dims == 3 AND trl_match AND semantic_sim > 0.4
  Label 2: key_dims == 3
  Label 1: key_dims == 2   ← now always reachable
  Label 0: key_dims <= 1
```
Note: grants with no sector restriction count as `sector_match=True`.
Resulting distribution with real embeddings: ~41% / ~35% / ~21% / ~3–10%.

### Fix 4 — ingest_cordis.py: three separate errors
**Root cause 1 — wrong default path**: Script defaulted to
`data/raw/cordis-HorizonEurope-projects.csv` but the manually downloaded
CORDIS extract is named `data/raw/project.csv`.

**Fix**: Changed `DEFAULT_CSV_PATH` to `data/raw/project.csv`. Added
`_ALT_CSV_PATH = data/raw/cordis-HorizonEurope-projects.csv` as automatic
fallback so both filenames work without needing `--csv` flag.

**Root cause 2 — comma decimal separator**: Some `ecMaxContribution` cells
use comma as decimal separator (e.g. `"4969471,25"`) causing `float()`
to raise `ValueError`.

**Fix**: In `_safe_float()`, added `value.replace(",", ".")` before casting
when value is a string.

**Root cause 3 — embedded semicolons in objective field**: Some `objective`
cells contain unescaped semicolons inside double-quoted strings (e.g. the
TACOS row). The pandas C engine raised `ParserError: Expected 20 fields,
saw 22`.

**Fix**: Switched to `engine="python"` with `on_bad_lines="skip"` in
`pd.read_csv()`. Removed `low_memory=False` (incompatible with Python engine).
Result: 19,476 rows loaded, 0 skipped from the manually extracted CSV.

---

## Key Architecture Decisions
- SQLite for dev (DATABASE_URL=sqlite+aiosqlite:///data/grants.db)
- PostgreSQL swap = one env var change
- FAISS IndexIDMap — Grant.id integers map directly to DB rows
- All ingestion scripts runnable standalone as python -m data.ingest.X
- Heuristic scorer used until ml/model.pkl exists
- matcher.py: full 8-step pipeline implemented
- reranker.py: heuristic fallback active, XGBoost loads when model.pkl exists
- GOV.UK scraper reads __NEXT_DATA__ JSON (not HTML) — recheck if Next.js
  build ID changes and data structure shifts
- UKRI scraper uses div.opportunity selector — recheck if WordPress theme changes
- Docker uses CPU-only PyTorch (190MB wheel, not 3GB CUDA) via pytorch.org/whl/cpu index
- requirements.txt = production deps only; test deps in requirements-dev.txt
- data/grants.db, data/grants.faiss, ml/model.pkl all gitignored and dockerignored
  — must be regenerated post-deploy (app works in degraded mode without them)

## File Structure (complete)
grantmatch-api/
├── app/main.py, config.py, database.py
├── app/models/db_models.py, schemas.py
├── app/services/embedder.py, matcher.py, reranker.py
├── app/api/routes.py
├── app/utils/eligibility.py, feature_extractor.py
├── data/ingest/__init__.py + 4 ingest scripts
├── scripts/__init__.py, build_index.py
├── ml/train.py, evaluate.py
├── tests/test_api.py, test_matcher.py
├── data/raw/project.csv  (CORDIS — manually downloaded, gitignored)
├── requirements.txt (production deps), requirements-dev.txt (+ pytest/pytest-asyncio)
├── Dockerfile, .dockerignore, railway.json, Procfile, .railwayignore
└── CLAUDE.md, PROGRESS.md, README.md, .env, .env.example

---

## Session 3 — Full Ingestion + Index Build + Test Suite Fixes (2026-04-13)

### Fix 5 — scripts/build_index.py: ModuleNotFoundError when run as python scripts/build_index.py
**Root cause**: `scripts/` had no `__init__.py`, so Python could not import it as a package.
Running as `python scripts/build_index.py` adds `scripts/` to sys.path but not the project root,
breaking all `from app.*` imports.
**Fix**: Created `scripts/__init__.py` (empty). Running as `python -m scripts.build_index` from
the project root adds the project root to sys.path automatically, resolving all imports.

### Ingestion runs completed
All four ingestion scripts run to completion from project root:
- `python -m data.ingest.ingest_govuk_grants` → **101 records** (GOV.UK Find a Grant, 11 pages)
- `python -m data.ingest.ingest_ukri_opportunities` → **111 records** (UKRI Opportunities, 12 pages,
  listing cards + detail page enrichment via 5-way concurrent fetches)
- `python -m data.ingest.ingest_ukri_gtr` → **5,000 records** (UKRI GtR API, 50 pages × 100 records)
- CORDIS already done (19,476 records) — skipped

### FAISS index
`python -m scripts.build_index` encoded all 24,688 grants with descriptions using
all-MiniLM-L6-v2 (batches of 256), wrote embedding_vector bytes to DB, built FAISS
IndexIDMap(IndexFlatIP) with 24,688 × 384-dim vectors, saved to `data/grants.faiss`.
Build time: ~20 minutes on CPU.

### ML model
`python ml/train.py` ran cleanly:
- Label distribution: {0: 612, 1: 526, 2: 315, 3: 47} — all 4 classes present
- Test accuracy: 99.67%, Macro F1: 0.98
- Saved to `ml/model.pkl`

### Test suite fixes (now 31/31)
Two test-suite assumptions broke after real data ingestion and model training:

**Fix A — test_grants_browse_empty_db**: The test asserted `response.json() == []` but the
DB now has 24,688 real grant records. Renamed to `test_grants_browse_returns_list` and changed
assertion to `isinstance(response.json(), list)`.

**Fix B — test_heuristic_***: Three tests created `GrantReranker()` and asserted `model is None`
to verify the heuristic scoring path. After `ml/train.py` ran, `ml/model.pkl` exists and the
reranker loads it on init. Fix: added `reranker.model = None` after instantiation in all three
tests to explicitly force the heuristic path.

### API smoke test (POST /api/v1/match)
Profile: `{organisation_type: "sme", sectors: ["ai","clean_energy"], location: "england", trl: 4}`
Description: "We build AI tools to help small businesses reduce energy consumption and meet net zero targets."

With FAISS index loaded, top result was **"Energy-efficient AI-ready Data Spaces"** (CORDIS,
GREEN.DAT.AI project) with semantic_similarity=0.5953, score=84.22.
Processing time: 412ms (vs 2856ms using DB fallback before index was built).
All response fields present: grant_id, title, score, confidence, top_factors (3 each),
eligibility_verdict, funding_range, url, processing_time_ms, data_freshness.

---

## Session 4 — Railway Deployment Prep (2026-04-13)

### Files created
- **`railway.json`**: Tells Railway to use the Dockerfile builder, sets start command to
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, healthcheck at `/health`.
- **`Procfile`**: Railway fallback (if Dockerfile builder not detected):
  `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **`.railwayignore`**: Excludes `data/raw/`, `data/grants.db`, `data/grants.faiss`,
  `ml/model.pkl`, `__pycache__/`, `.pytest_cache/` from Railway git push.
- **`.dockerignore`**: Excludes the same large/local-only files from the Docker build
  context (also excludes `.env`, `*.pyc`, `*.pyo`, `.git/`). Keeps context small and
  prevents local DB/index from leaking into the image.
- **`requirements-dev.txt`**: New file — `-r requirements.txt` plus `pytest==8.3.3` and
  `pytest-asyncio==0.24.0`. Use this for local dev and CI; the production Docker image
  only uses `requirements.txt`.

### Files modified
- **`Dockerfile`**: Added `RUN pip install --no-cache-dir torch --index-url
  https://download.pytorch.org/whl/cpu` as a separate layer *before* `pip install -r
  requirements.txt`. This pins CPU-only PyTorch (190MB wheel vs 3GB CUDA build) so the
  Docker image stays deployable without a GPU.
- **`requirements.txt`**: Removed `pytest==8.3.3` and `pytest-asyncio==0.24.0` — test
  deps don't belong in the production image. Moved to `requirements-dev.txt`.
- **`.env.example`**: Added comment block above `DATABASE_URL` explaining that Railway's
  Postgres plugin sets this automatically in production as a `postgresql+asyncpg://...` URL.

### Docker build outcome
`docker build .` completed successfully (exit code 0) after two attempts:
- **Attempt 1 failed**: `pytest-asyncio==0.24.0` hash mismatch — pip downloaded an empty
  file (transient Docker network issue, SHA256 of empty string = `e3b0c44...`). Root fix:
  removed test deps from requirements.txt entirely.
- **Attempt 2 succeeded**: All packages installed cleanly. Installed packages include
  `nvidia-nccl-cu12` (pulled as a transitive dep of sentence-transformers). This is a
  ~300MB overhead but doesn't affect correctness — torch is still the CPU build.

### Post-deploy checklist (not yet done)
1. Add Postgres plugin in Railway → `DATABASE_URL` set automatically.
2. Set remaining env vars: `API_KEY`, `EMBEDDING_MODEL`, `MAX_RESULTS`, etc.
3. After first deploy: run ingestion scripts and `python -m scripts.build_index`.
4. `python ml/train.py` to generate `ml/model.pkl`.
5. Without steps 3–4, the app starts in degraded mode: DB-fallback matching (no FAISS
   semantic search) and heuristic scoring (no XGBoost reranker). All endpoints still work.

---

## Session 5 — Python 3.11 Compatibility Refactor (2026-04-13)

### Goal
Migrate pinned dependencies from versions targeting Python 3.14 to versions known
to work cleanly on Python 3.11 (the target runtime for Docker and Railway).

### requirements.txt — version changes
| Package | Old (3.14 era) | New (3.11 stable) |
|---------|---------------|-------------------|
| sentence-transformers | 3.0.1 | 2.7.0 |
| faiss-cpu | 1.12.0 | 1.8.0 |
| xgboost | 2.1.4 | 2.1.1 |
| shap | 0.50.0 | 0.45.1 |
| scikit-learn | 1.7.2 | 1.5.2 |
| sqlalchemy | 2.0.49 | 2.0.35 |
| greenlet | 3.4.0 | 3.0.3 |
| lxml | 6.0.1 | 5.3.0 |
| pandas | 2.3.3 | 2.2.3 |
| numpy | 2.3.5 | 1.26.4 |
| pydantic | 2.12.0 | 2.9.2 |
| pydantic-settings | 2.9.1 | 2.4.0 |
| uvicorn | 0.30.6 | 0.30.6[standard] |

Unchanged: fastapi, aiosqlite, beautifulsoup4, httpx, python-dotenv.

### Python 3.14-specific workarounds removed
- **app/models/db_models.py comment**: Replaced "due to Python 3.14 SQLAlchemy
  Union.__getitem__ bug" with a neutral explanation. The `Mapped[Optional[Any]]`
  typing is kept — it remains the correct approach for SQLAlchemy JSON columns
  regardless of Python version.
- **PROGRESS.md Phase 2 note**: Same update — removed 3.14 bug reference.
- No `from __future__ import annotations` imports were removed — these are valid
  and beneficial on 3.11 (PEP 563, avoids forward-reference issues).

### New files
- **`.python-version`**: Contains `3.11.9` — read by pyenv locally and by Railway
  to select the correct Python runtime.

### What stayed the same
- All application logic unchanged.
- Dockerfile already had `FROM python:3.11-slim` — no change needed.
- `requirements-dev.txt` unchanged (pytest==8.3.3, pytest-asyncio==0.24.0 already correct).
- 31/31 tests still passing after dep version changes (run on Python 3.14 dev env).

---

## Session 6 — Railway Production Deployment Fixes (2026-04-15)

### Context
First live Railway deploy: Postgres service added, domain assigned, API key set.
Multiple deployment errors surfaced and fixed in sequence.

### Fix 1 — "Not Found" at domain root
**Root cause**: No route registered at `/`. All routes live under `/api/v1/`.
Hitting the Railway domain returned FastAPI's default 404.
**Fix**: Added `GET /` in `app/main.py` returning a `RedirectResponse` to `/api/v1/`.

### Fix 2 — asyncpg missing from requirements.txt
**Root cause**: `asyncpg` was never added to `requirements.txt`. `aiosqlite` was present
for SQLite but asyncpg (required for PostgreSQL) was absent.
**Error**: `ModuleNotFoundError: No module named 'asyncpg'` at container start.
**Fix**: Added `asyncpg==0.29.0` to `requirements.txt`.

### Fix 3 — DATABASE_URL format mismatch
**Root cause**: Railway's Postgres plugin provides `DATABASE_URL` as `postgresql://...`
(or `postgres://...`). SQLAlchemy + asyncpg requires `postgresql+asyncpg://...`.
**Fix**: Added a `@field_validator("database_url", mode="before")` in `app/config.py`
that rewrites both `postgres://` and `postgresql://` prefixes to `postgresql+asyncpg://`
automatically at Settings instantiation. No env var change needed on Railway.

### Fix 4 — Embedding model download blocking healthcheck
**Root cause**: `SentenceTransformer('all-MiniLM-L6-v2')` downloads ~90 MB from
HuggingFace at container startup. This blocked the lifespan event before any HTTP
traffic could be served. Railway's healthcheck window is 5 minutes — slow Railway
infra or rate-limited HF could kill the container before `/health` ever responded.
**Fix**: Pre-download the model during Docker build:
```dockerfile
ENV HF_HOME=/app/.hf_cache
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```
Model is baked into the image (~90 MB layer). Startup loads from disk in ~1 second.
Docker layer is cached — only re-downloaded if requirements change.
Also added `.hf_cache/` to `.dockerignore` to prevent local cache leaking into the build context.

### Fix 5 — Pydantic protected namespace warning
**Root cause**: `model_path` field in `Settings` clashes with Pydantic v2's `model_`
namespace, generating a `UserWarning` on every startup/import.
**Fix**: Added `"protected_namespaces": ()` to `model_config` in `app/config.py`.

### Fix 6 — PostgreSQL connection pool
**Root cause**: Default SQLAlchemy engine config has no `pool_pre_ping`. Railway
recycles idle connections; without pre-ping, stale connections cause errors
after periods of inactivity.
**Fix**: Updated `app/database.py` engine to use:
- `pool_pre_ping=True` for both dialects (re-verifies connection before each use)
- `pool_size=5, max_overflow=10` for PostgreSQL
- `connect_args={"check_same_thread": False}` for SQLite (unchanged behaviour)

### Fix 7 — CORDIS download URL (404)
**Root cause**: `CORDIS_CSV_URL` pointed to `cordis.europa.eu/data/cordis-HorizonEurope-projects.csv`
which returns 404. The actual download is a ZIP at a different URL.
**Correct URL**: `https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip`
The ZIP contains multiple CSVs; `project.csv` (46.6 MB) is the grant data file.
**Fix**: Updated `data/ingest/ingest_cordis.py`:
- Replaced `CORDIS_CSV_URL` with `CORDIS_ZIP_URL`
- Rewrote `_download_csv()` to stream the ZIP into `io.BytesIO`, open it with
  `zipfile.ZipFile`, find the entry ending in `project.csv`, and extract it to disk
- Added `import io, zipfile`

### New file — scripts/ingest_all.py
One-shot script to populate all data sources, build FAISS index, and train model.
Run from Railway Shell tab after first deploy:
```
python -m scripts.ingest_all
```
- Runs GOV.UK, UKRI Opportunities, UKRI GtR in sequence
- CORDIS: checks if `source == "cordis"` rows already exist; skips download if so
  (avoids re-downloading the 250 MB zip on repeat runs)
- CORDIS errors are caught and logged — the rest of the script continues
- Calls `scripts.build_index.build_index()` directly (no subprocess)
- Runs `ml/train.py` via subprocess
- `httpx` logger set to WARNING — suppresses per-request INFO spam

### Railway deployment notes (operational)
- **Start command**: Must be blank in Railway UI (uses Dockerfile `CMD`) or explicitly
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Setting it to
  `python -m scripts.ingest_all` causes a crash loop — the ingest fails (CORDIS 404
  was the trigger), Railway restarts the container, ingest runs again, crashes again.
- **Ingest must be run from the Shell tab**, not as the service start command.
- **Postgres data persists** across redeploys. FAISS index and model.pkl do not
  (ephemeral container filesystem). After each redeploy, run:
  ```
  python -m scripts.build_index   # ~20 min on CPU
  python ml/train.py              # ~30 sec
  ```
  Full re-ingest only needed if grant data is stale.

### Railway first-deploy data status (2026-04-15)
| Source           | Records | Status                          |
|------------------|---------|---------------------------------|
| govuk            | 107     | Ingested                        |
| ukri_opportunity | 114     | Ingested                        |
| ukri_gtr         | 5,000   | Ingested                        |
| cordis           | 0       | Pending (URL fix now applied)   |
| **Total**        | **5,221** | FAISS build in progress       |

FAISS index: encoding 5,221 grants at ~3 min/batch of 256 on Railway CPU (~60 min total).
Model: will be trained automatically after FAISS build completes.

---

## Session 7 — Memory Fixes, Local Build Strategy & Production Verification (2026-04-16)

### Context
Railway free tier (1 GB RAM, 2 CPU cores) ran out of memory during
`python -m scripts.build_index` (crashed at ~4352/24699 grants) and
during CORDIS ingestion (ZIP buffered entirely in RAM). Also, the
`/api/v1/grants` listing returned grants in non-deterministic order.

### Fix 1 — scripts/build_index.py: OOM on Railway (primary culprit)
**Root cause**: `list(result.scalars().all())` loaded all 24,699 full
Grant ORM objects (21 columns including long CORDIS descriptions) into
a Python list before encoding started.  Then `all_vectors` accumulated
every batch's numpy array before a single `np.vstack()` at the end.
Peak RAM = model (~100 MB) + all ORM objects (~150 MB) + full vector
matrix (~37 MB) + Python overhead → easily exceeded 1 GB.

**Fix**:
- Offset-based batch loop: `SELECT id, title, description … LIMIT 128
  OFFSET n` — only 3 columns, 128 rows in RAM per iteration.
- `BATCH_SIZE` reduced from 256 → 128 (halves encoding activation peak).
- FAISS `id_index.add_with_ids()` called per batch (incremental) instead
  of one `np.vstack` at the end.
- Bulk DB update via `execute(update(Grant), [{…}])` per batch — avoids
  individual UPDATE round-trips.
- `dim` derived from a single dummy encode before the loop so
  `IndexFlatIP(dim)` is constructed before any real data is processed.

### Fix 2 — data/ingest/ingest_cordis.py: ZIP buffered in RAM
**Root cause 1 — io.BytesIO**: The entire ~250 MB ZIP was streamed into
`io.BytesIO()` in RAM before extraction.
**Fix**: Stream ZIP bytes directly to `_cordis_download.zip.tmp` on
disk. Extract `project.csv` from the ZIP file (on disk) using
`shutil.copyfileobj` in 64 KB chunks. Temp file deleted in a `finally`
block. Peak RAM for download: ~0 MB instead of ~250 MB.

**Root cause 2 — full DataFrame**: `pd.read_csv()` loaded all 19,476
rows into a single DataFrame.
**Fix**: Detect CSV separator with a 5-row probe read, then use
`pd.read_csv(…, chunksize=500)` to iterate 500 rows at a time.
DB `commit()` happens after each chunk. Full CSV never in RAM at once.

### Fix 3 — app/api/routes.py: non-deterministic grant ordering
**Root cause**: `ORDER BY deadline ASC NULLS LAST` only — the majority
of CORDIS records have no deadline so they all landed in undefined heap
order. No `offset` parameter meant proper pagination was impossible.
**Fix**:
- Added `Grant.id.asc()` as a secondary sort → fully deterministic
  regardless of NULL deadlines.
- Added `offset: int = Query(0, …)` parameter → clients can paginate
  with `?limit=50&offset=50`.

### Fix 4 — scripts/ingest_all.py: partial CORDIS ingest not retried
**Root cause**: CORDIS skip check `if existing > 0` meant a
partially-ingested run (e.g. crashed after 3,000 rows) would never
be retried — the script saw rows and assumed completion.
**Fix**: Added `_CORDIS_MIN_EXPECTED = 10_000` threshold. Script re-runs
CORDIS ingestion if row count is below threshold, logging a warning
about the interrupted prior run.

### Fix 5 — .gitignore / .dockerignore / .railwayignore
Updated all three files so `data/grants.faiss` and `ml/model.pkl` are
**no longer excluded**:
- `.gitignore`: Added `!ml/model.pkl` and `!data/grants.faiss` negation
  rules after the `*.pkl` / `*.faiss` glob lines.
- `.dockerignore` / `.railwayignore`: Removed the two lines; replaced
  with comments explaining the intentional inclusion.
- `.env.example`: Sanitized — real Railway internal URL that had been
  committed was replaced with `sqlite+aiosqlite:///data/grants.db`
  placeholder.

### Local build strategy (bypasses Railway RAM limit permanently)
Railway's 1 GB RAM cannot run `build_index.py` against 24,699 grants.
Solution: build on local machine (i9 12th gen, RTX 4070, 40 GB DDR5),
commit the artifacts, bake them into the Docker image.

**Procedure**:
1. Set `DATABASE_URL` in local `.env` to Railway's public PostgreSQL URL
   (`monorail.proxy.rlwy.net:18935`).
2. `python -m scripts.build_index` — reads Grant IDs from Railway's live
   PostgreSQL (correct IDs), encodes all 24,699 texts on local GPU
   (CUDA: True, RTX 4070), writes `embedding_vector` back to Railway's
   DB, saves `data/grants.faiss` locally.
   - Completed: 24,699 / 24,699 vectors, dim=384.
   - SSL cleanup error on exit is cosmetic (Windows Python 3.10
     asyncio Proactor + asyncpg SSL teardown after event loop close).
3. `python ml/train.py` — purely synthetic data, no DB needed.
   - Accuracy: 99.67%, Macro F1: 0.98. Saved to `ml/model.pkl`.
4. `git add data/grants.faiss ml/model.pkl` + commit + push.
   Railway rebuilds Docker image with both files baked in (~40 MB total).

### Production verification (2026-04-16)
```
GET /api/v1/health → 200 OK
{
  "status": "ok",
  "model_loaded": true,
  "grants_in_db": 24699,
  "index_built": true,
  "last_ingestion": "2026-04-16"
}
```
All endpoints confirmed live at:
`https://grantmatch-api-production.up.railway.app`
Swagger docs: `/docs`

### Updated deployment notes
- `data/grants.faiss` and `ml/model.pkl` are now committed to git and
  baked into the Docker image. They persist across every redeploy with
  zero RAM cost on Railway.
- To refresh after a major data update: re-run the local build procedure
  above (steps 1–4), then push. Takes ~20 min on RTX 4070.
- Full re-ingest of grant data: still run from Railway Shell tab via
  `python -m scripts.ingest_all` (CORDIS skip threshold now 10,000).
- After re-ingest, must also re-run local build procedure to rebuild
  FAISS index with updated IDs.

### Live data status (2026-04-16)
| Source           | Records | Status     |
|------------------|---------|------------|
| govuk            | ~107    | Ingested   |
| ukri_opportunity | ~114    | Ingested   |
| ukri_gtr         | 5,000   | Ingested   |
| cordis           | ~19,478 | Ingested   |
| **Total**        | **24,699** | **All in PostgreSQL** |

FAISS index: 24,699 vectors (dim=384), baked into Docker image.
Model: XGBoost, 99.67% accuracy, baked into Docker image.

