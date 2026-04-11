# GrantMatch API

ML-scored grant matching API. Accepts an applicant profile, returns ranked matching UK and EU grants with fit scores, eligibility signals, and deadlines.

## Quick start

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Or with Docker:

```bash
docker-compose up --build
```

API docs available at `http://localhost:8000/docs`.
