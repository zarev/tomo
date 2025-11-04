# TOMO PoC (local menubar AI companion) - PoC scaffold

This repository contains a minimal PoC scaffold for the TOMO project: a local
Postgres+pgvector instance and a tiny FastAPI backend that demonstrates storing
and retrieving vector memories using a deterministic (small) embedder.

What is included:
- `docker-compose.yml` — starts Postgres with pgvector
- `backend/` — minimal FastAPI backend, a deterministic embedder, DB helpers, and SQL migration

Quickstart (Linux/macOS):

1) Start Postgres with pgvector:

```bash
docker compose up -d
```

2) (Optional) Create a virtualenv and install backend deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

3) Run the backend (it will attempt to run migrations on startup):

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

4) Try API endpoints:

- POST http://127.0.0.1:8000/talk with JSON { "text": "hello tomo" }
- POST http://127.0.0.1:8000/memories/search with JSON { "text": "hello" }

Notes / next steps:
- This PoC uses a deterministic placeholder embedder; swap it for a real
  embedding model (local small model or llama.cpp embedding) for semantic recall.
- Next tasks: wire llama.cpp for inference, add a Tauri menubar UI, implement
  the pet tick loop and memory summarization jobs.
