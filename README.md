# GrantMatch API

ML-scored grant matching for UK and EU funding — returns ranked grants with fit scores, eligibility signals, and top-3 explanation factors for any company or research profile.

---

## Quick start

```bash
git clone https://github.com/your-org/grantmatch-api.git
cd grantmatch-api
cp .env.example .env
pip install -r requirements.txt
```

---

## Data ingestion

Run one or more sources to populate the grant database:

```bash
# UK government grants (GOV.UK Find a Grant)
python -m data.ingest.ingest_govuk_grants

# Live Innovate UK / UKRI competitions
python -m data.ingest.ingest_ukri_opportunities

# UKRI Gateway to Research (historical funded projects)
python -m data.ingest.ingest_ukri_gtr

# Horizon Europe CORDIS (bulk CSV — download manually first)
# 1. Download from https://data.europa.eu/data/datasets (he_project CSV)
# 2. Place in data/raw/cordis_projects.csv
python -m data.ingest.ingest_cordis
```

---

## Build search index

After ingestion, build the FAISS vector index:

```bash
python -m scripts.build_index
```

---

## Train reranker model

Generate synthetic training data and train the XGBoost reranker:

```bash
python ml/train.py
```

Outputs `ml/model.pkl`. The API uses a weighted heuristic automatically if the model file is absent.

---

## Run server

```bash
uvicorn app.main:app --reload
```

Or with Docker:

```bash
docker-compose up
```

API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Example request

```bash
curl -X POST http://localhost:8000/api/v1/match \
  -H "Content-Type: application/json" \
  -H "X-API-Key: changeme" \
  -d '{
    "organisation_name": "CropVision Ltd",
    "organisation_type": "sme",
    "description": "We develop drone-based multispectral imaging and AI analytics to help UK farmers monitor crop health, optimise irrigation, and reduce pesticide use. Field trials have demonstrated a 20% yield improvement.",
    "sectors": ["agritech", "ai"],
    "location": "england",
    "trl": 4,
    "funding_needed": 150000,
    "top_n": 3
  }'
```

## Example response

```json
{
  "profile_summary": "We develop drone-based multispectral imaging and AI analytics to help UK farmers...",
  "total_matched": 3,
  "processing_time_ms": 142.5,
  "data_freshness": "2024-11-01",
  "grants": [
    {
      "grant_id": 12,
      "title": "Innovate UK AI Innovation Fund — Round 1",
      "funder": "Innovate UK",
      "summary": "Funding for SMEs developing AI-based solutions that address productivity challenges.",
      "score": 87.4,
      "confidence": 0.87,
      "status": "open",
      "deadline": "2025-03-31T00:00:00",
      "funding_range": "£50k – £300k",
      "eligibility_verdict": "likely_eligible",
      "top_factors": [
        { "factor_name": "sector_overlap",      "direction": "positive", "impact": 0.8 },
        { "factor_name": "semantic_similarity", "direction": "positive", "impact": 0.76 },
        { "factor_name": "org_type_match",      "direction": "positive", "impact": 1.0 }
      ],
      "url": "https://apply-for-innovation-funding.service.gov.uk/competition/12"
    },
    {
      "grant_id": 7,
      "title": "BBSRC Strategic Longer and Larger Grant",
      "funder": "BBSRC / UKRI",
      "summary": "Large grants for bioscience research programmes in UK universities.",
      "score": 41.2,
      "confidence": 0.41,
      "status": "open",
      "deadline": "2025-06-15T00:00:00",
      "funding_range": "£500k – £2.0m",
      "eligibility_verdict": "check_required",
      "top_factors": [
        { "factor_name": "semantic_similarity", "direction": "positive", "impact": 0.61 },
        { "factor_name": "org_type_match",      "direction": "negative", "impact": 0.0 },
        { "factor_name": "sector_overlap",      "direction": "positive", "impact": 0.33 }
      ],
      "url": null
    },
    {
      "grant_id": 21,
      "title": "Net Zero Innovation Portfolio — Low Carbon Heat",
      "funder": "DESNZ / BEIS",
      "summary": "Grants for innovators developing low-carbon heat technologies.",
      "score": 35.8,
      "confidence": 0.36,
      "status": "open",
      "deadline": "2025-02-28T00:00:00",
      "funding_range": "£100k – £750k",
      "eligibility_verdict": "check_required",
      "top_factors": [
        { "factor_name": "semantic_similarity", "direction": "positive", "impact": 0.44 },
        { "factor_name": "region_match",        "direction": "positive", "impact": 1.0 },
        { "factor_name": "sector_overlap",      "direction": "negative", "impact": 0.0 }
      ],
      "url": null
    }
  ]
}
```

---

## Endpoints

| Method | Path                   | Auth required | Description                            |
|--------|------------------------|:-------------:|----------------------------------------|
| GET    | `/api/v1/`             | No            | API info and links                     |
| GET    | `/api/v1/health`       | No            | Health check — model, DB, index status |
| POST   | `/api/v1/match`        | Yes           | Match a profile against grants         |
| GET    | `/api/v1/grants`       | Yes           | Browse grants (filter by status/sector)|
| GET    | `/api/v1/grants/{id}`  | Yes           | Retrieve a single grant by ID          |
| GET    | `/health`              | No            | Lightweight probe for load balancers   |
| GET    | `/docs`                | No            | Interactive Swagger UI                 |

Authentication uses the `X-API-Key` request header. Set `API_KEY` in `.env`.

---

## Pricing

| Tier          | Price           | Requests          |
|---------------|-----------------|-------------------|
| Free          | £0/month        | 50 requests/month |
| Pro           | £149/month      | Unlimited         |
| Enterprise    | Contact us      | Custom SLA + data |

---

## Interactive docs

`http://localhost:8000/docs`
