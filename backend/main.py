"""Minimal FastAPI backend for TOMO PoC.

Endpoints:
- POST /talk { pet_id?, text } -> saves a memory, returns a mock reply
- POST /memories/search { text, k?, pet_id? } -> returns nearest memories
- GET /health -> basic liveness

This PoC uses a deterministic local embedder (no external models required).
"""
import os
from typing import Any, Dict, List, Optional
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .embedder import EMBED_DIM, text_to_embedding, vec_to_pgvector_literal
from .db import insert_memory, run_migrations, search_memories
from .llm_client import embed as llama_embed, completion as llama_completion, health as llama_health


class TalkRequest(BaseModel):
    pet_id: Optional[str] = None
    text: str


class TalkResponse(BaseModel):
    reply: str
    memory_id: Optional[str] = None
    memory_content: Optional[str] = None


class SearchRequest(BaseModel):
    text: str
    k: Optional[int] = 5
    pet_id: Optional[str] = None


app = FastAPI(title="tomo-poc-backend")

# Serve the simple frontend for PoC from ../frontend
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(frontend_dir):
    # Serve static files under /static to avoid shadowing API routes
    app.mount("/static", StaticFiles(directory=frontend_dir), name="frontend_static")

    # Serve the SPA index at root
    @app.get("/", include_in_schema=False)
    def root_index():
        index = os.path.join(frontend_dir, "index.html")
        if os.path.isfile(index):
            return FileResponse(index, media_type="text/html")
        raise HTTPException(status_code=404, detail="Index not found")


@app.on_event("startup")
def startup():
    # Run migrations automatically for PoC
    try:
        run_migrations()
    except Exception as e:
        # Log but allow server to start; health/DB errors will show later
        print("Migration error:", e)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/talk", response_model=TalkResponse)
def talk(req: TalkRequest) -> TalkResponse:
    if not req.text:
        raise HTTPException(status_code=400, detail="text is required")

    # Try to get an embedding from a local model; fallback to deterministic embedder
    try:
        emb = llama_embed(req.text)
    except Exception:
        emb = None
    if emb is None:
        emb = text_to_embedding(req.text)

    if emb.shape[0] != EMBED_DIM:
        # If dims don't match, coerce/truncate/pad to EMBED_DIM
        arr = np.asarray(emb, dtype=float)
        if arr.size > EMBED_DIM:
            emb = arr[:EMBED_DIM]
        else:
            # pad with zeros
            emb = np.concatenate([arr, np.zeros(EMBED_DIM - arr.size, dtype=float)])

    emb_literal = vec_to_pgvector_literal(emb)
    # persist memory (simple category 'interaction')
    row = insert_memory(req.pet_id, req.text, emb_literal, category="interaction")

    # Try to get a completion from local llama server; fallback to deterministic echo
    try:
        reply = llama_completion(req.text)
    except Exception:
        reply = None
    if not reply:
        summary = req.text.strip().replace('\n', ' ')[:120]
        reply = f"Tomo: I heard '{summary}'. Thanks for sharing!"

    return TalkResponse(
        reply=reply,
        memory_id=row.get("id"),
        memory_content=req.text,
    )


@app.post("/api/memories/search")
def memories_search(req: SearchRequest) -> List[Dict[str, Any]]:
    emb = text_to_embedding(req.text)
    emb_literal = vec_to_pgvector_literal(emb)
    rows = search_memories(emb_literal, pet_id=req.pet_id, k=req.k or 5)
    return rows


@app.get("/api/model/status")
def model_status() -> Dict[str, Any]:
    running = llama_health()
    return {"running": running, "url": os.environ.get("LLAMA_SERVER_URL", "http://127.0.0.1:8080")}

