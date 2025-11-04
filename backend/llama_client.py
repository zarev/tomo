"""Small adapter to call a local llama.cpp HTTP server with graceful fallbacks.

This adapter tries a few common endpoints for embeddings and completions. If the
server isn't available or responses aren't in an expected shape, it falls back
to the deterministic embedder and a simple mock completion so the PoC remains
usable without a running LLM.
"""
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import numpy as np
import requests

from .embedder import text_to_embedding

# Config
LLAMA_URL = os.environ.get("LLAMA_SERVER_URL", "http://127.0.0.1:8080")
REQUEST_TIMEOUT = float(os.environ.get("LLAMA_REQUEST_TIMEOUT", "5.0"))

# Internal process handle for a server started by this adapter (if any)
_proc: Optional[subprocess.Popen] = None


def _try_post(path: str, json: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Optional[requests.Response]:
    url = LLAMA_URL.rstrip("/") + path
    try:
        resp = requests.post(url, json=json, timeout=timeout)
        if resp.status_code == 200:
            return resp
    except requests.RequestException:
        return None
    return None


def health() -> bool:
    """Check server liveness.

    If we started a local server process, prefer checking that process; otherwise
    try a few well-known HTTP endpoints.
    """
    global _proc
    if _proc is not None:
        # check if process still running
        return _proc.poll() is None

    # Try HTTP probes
    try:
        r = requests.get(LLAMA_URL, timeout=1.0)
        if r.status_code == 200:
            return True
    except requests.RequestException:
        pass
    try:
        r = requests.get(LLAMA_URL.rstrip("/") + "/health", timeout=1.0)
        if r.status_code == 200:
            return True
    except requests.RequestException:
        pass
    return False


def start_server(cmd: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
    """Start a local server process using the provided command list.

    Returns a dict with keys: running (bool), pid (int|None) and started (bool).
    If a server is already running that we started, it will be returned instead of
    starting another process.
    """
    global _proc
    if _proc is not None and _proc.poll() is None:
        return {"running": True, "pid": _proc.pid, "started": False}

    # Start the process
    _proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # give it a short moment to start
    time.sleep(0.5)
    return {"running": _proc.poll() is None, "pid": _proc.pid if _proc else None, "started": True}


def stop_server() -> Dict[str, Any]:
    """Stop the server process started by start_server (if any)."""
    global _proc
    if _proc is None:
        return {"stopped": True, "pid": None}
    try:
        _proc.terminate()
        _proc.wait(timeout=5.0)
    except Exception:
        try:
            _proc.kill()
        except Exception:
            pass
    pid = _proc.pid
    _proc = None
    return {"stopped": True, "pid": pid}


def embed(text: str) -> np.ndarray:
    """Return a numpy embedding for text.

    Attempts to call a running llama.cpp server; if unavailable, fall back to
    the deterministic embedder in `embedder.py`.
    """
    # Try common endpoints: /embed, /embeddings, /v1/embeddings
    candidates = ["/embed", "/embeddings", "/v1/embeddings"]
    payload_variants = [{"text": text}, {"input": text}, {"inputs": [text]}]

    for path in candidates:
        for payload in payload_variants:
            resp = _try_post(path, payload)
            if resp is None:
                continue
            try:
                data = resp.json()
                # Try common response shapes
                if isinstance(data, dict):
                    if "embedding" in data and isinstance(data["embedding"], list):
                        return np.array(data["embedding"], dtype=float)
                    if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                        # e.g. {data: [{embedding: [...]}, ...]}
                        first = data["data"][0]
                        if isinstance(first, dict) and "embedding" in first:
                            return np.array(first["embedding"], dtype=float)
            except Exception:
                continue

    # fallback
    return text_to_embedding(text)


def completion(prompt: str, n_predict: int = 128, temperature: float = 0.7) -> str:
    """Request a completion from a local llama.cpp server or return a mock reply.

    Tries common endpoints (/completion, /generate, /v1/completions). If none
    are available, returns a deterministic short reply.
    """
    candidates = ["/completion", "/generate", "/v1/completions", "/v1/completion"]
    payload_variants = [
        {"prompt": prompt, "n_predict": n_predict, "temperature": temperature},
        {"input": prompt, "n_predict": n_predict, "temperature": temperature},
        {"text": prompt, "max_tokens": n_predict, "temperature": temperature},
    ]

    for path in candidates:
        for payload in payload_variants:
            resp = _try_post(path, payload, timeout=max(REQUEST_TIMEOUT, 10.0))
            if resp is None:
                continue
            try:
                data = resp.json()
                # Try extracting text from common shapes
                if isinstance(data, dict):
                    if "response" in data and isinstance(data["response"], str):
                        return data["response"]
                    if "text" in data and isinstance(data["text"], str):
                        return data["text"]
                    if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        if isinstance(choice, dict) and "text" in choice:
                            return choice["text"]
                    if "results" in data and isinstance(data["results"], list) and len(data["results"]) > 0:
                        res = data["results"][0]
                        if isinstance(res, dict):
                            if "text" in res:
                                return res["text"]
                            if "response" in res:
                                return res["response"]
                # If response is plain text
                if resp.text:
                    return resp.text.strip()
            except Exception:
                continue

    # Final fallback: short deterministic echo-style reply
    summary = prompt.strip().replace('\n', ' ')[:120]
    return f"Tomo: I heard '{summary}'. (model unavailable)"
