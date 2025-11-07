"""HTTP adapter that talks to a running llama.cpp-style HTTP server.

This module intentionally provides a small, well-scoped interface used by
the rest of the backend: `embed(text)`, `completion(prompt)`, and
`health()`.

Configuration via environment variables:
- LLAMA_SERVER_URL - URL of the running server (default: http://llama:8080)
"""
import os
from typing import Any, Dict, Optional

import numpy as np
import requests
import logging

logger = logging.getLogger("llm_client")
logging.basicConfig(level=logging.INFO)

LLAMA_SERVER_URL = os.environ.get("LLAMA_SERVER_URL", "http://llama:8080")
REQUEST_TIMEOUT = float(os.environ.get("LLAMA_REQUEST_TIMEOUT", "5.0"))


def _try_post(path: str, json: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Optional[requests.Response]:
    url = LLAMA_SERVER_URL.rstrip("/") + path
    try:
        resp = requests.post(url, json=json, timeout=timeout)
        if resp.status_code == 200:
            return resp
    except requests.RequestException:
        logger.debug("Request to %s failed", url)
    return None


def health() -> bool:
    try:
        resp = requests.get(LLAMA_SERVER_URL, timeout=1.0)
        if resp is not None and resp.status_code == 200:
            return True
    except requests.RequestException:
        pass
    try:
        resp = requests.get(LLAMA_SERVER_URL.rstrip("/") + "/health", timeout=1.0)
        if resp is not None and resp.status_code == 200:
            return True
    except requests.RequestException:
        pass
    return False


def embed(text: str) -> Optional[np.ndarray]:
    """Request an embedding from the llama HTTP server.

    We try a few common endpoint paths and payload shapes. Returns a numpy
    array on success or None on failure.
    """
    candidates = [
        "/embed",
        "/embeddings",
        "/v1/embeddings",
    ]
    payloads = [{"text": text}, {"input": text}, {"inputs": [text]}]

    for path in candidates:
        for payload in payloads:
            resp = _try_post(path, payload)
            if resp is None:
                continue
            try:
                data = resp.json()
            except Exception:
                continue

            # common shapes
            if isinstance(data, dict):
                if "embedding" in data and isinstance(data["embedding"], list):
                    return np.array(data["embedding"], dtype=float)
                if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    first = data["data"][0]
                    if isinstance(first, dict) and "embedding" in first:
                        return np.array(first["embedding"], dtype=float)
                if "embeddings" in data and isinstance(data["embeddings"], list) and len(data["embeddings"]) > 0:
                    return np.array(data["embeddings"][0], dtype=float)

    return None


def completion(prompt: str, n_predict: int = 128, temperature: float = 0.7) -> Optional[str]:
    """Request a completion from the llama HTTP server.

    Tries a few endpoint and payload shapes and returns text on success.
    """
    candidates = ["/generate", "/completion", "/v1/completions"]
    payloads = [
        {"prompt": prompt, "n_predict": n_predict, "temperature": temperature},
        {"input": prompt, "max_tokens": n_predict},
        {"text": prompt, "max_tokens": n_predict},
    ]

    for path in candidates:
        for payload in payloads:
            resp = _try_post(path, payload, timeout=max(REQUEST_TIMEOUT, 10.0))
            if resp is None:
                continue
            try:
                data = resp.json()
            except Exception:
                if resp.text:
                    return resp.text.strip()
                continue

            if isinstance(data, dict):
                if "text" in data and isinstance(data["text"], str):
                    return data["text"]
                if "response" in data and isinstance(data["response"], str):
                    return data["response"]
                if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
                    ch = data["choices"][0]
                    if isinstance(ch, dict) and "text" in ch:
                        return ch["text"]
                if "results" in data and isinstance(data["results"], list) and len(data["results"]) > 0:
                    res = data["results"][0]
                    if isinstance(res, dict) and "text" in res:
                        return res["text"]

            if resp.text:
                return resp.text.strip()

    return None
