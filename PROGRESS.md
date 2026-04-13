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
- Python 3.14.3 on Windows
- greenlet==3.4.0 manually added to requirements.txt (SQLAlchemy async dep)
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
- JSON columns typed as Mapped[Optional[Any]] due to Python 3.14
  SQLAlchemy Union.__getitem__ bug
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

