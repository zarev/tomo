"""Minimal Gemini API adapter.

This adapter is intentionally small and conservative: it reads the following
environment variables to locate and authenticate with the Gemini/Generative API:

- GEMINI_API_KEY: Bearer key for Authorization header (required)
- GEMINI_BASE_URL: Base URL for the API (default: none, must be set if not using public defaults)
- GEMINI_EMBED_MODEL: model name for embeddings (optional)
- GEMINI_TEXT_MODEL: model name for text generation (optional)

The exact endpoints and request shapes vary across providers and API versions,
so this adapter attempts a few common endpoint patterns and response shapes and
falls back cleanly by returning None on errors.
"""
import os
from typing import Any, Dict, Optional

import numpy as np
import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_BASE_URL = os.environ.get("GEMINI_BASE_URL", "")
EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "")
TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "")


def _auth_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}


def _post(url: str, json: Dict[str, Any], timeout: float = 10.0) -> Optional[requests.Response]:
    if not GEMINI_API_KEY or not url:
        return None
    try:
        return requests.post(url, json=json, headers=_auth_headers(), timeout=timeout)
    except requests.RequestException:
        return None


def embed(text: str) -> Optional[np.ndarray]:
    """Return embedding as numpy array, or None on failure.

    Tries a few common endpoint suffixes and payload shapes.
    """
    if not GEMINI_API_KEY or not GEMINI_BASE_URL:
        return None

    model = EMBED_MODEL or "embedding-model"
    candidates = [
        f"{GEMINI_BASE_URL.rstrip('/')}/v1/models/{model}:embed",
        f"{GEMINI_BASE_URL.rstrip('/')}/v1/models/{model}:embedText",
        f"{GEMINI_BASE_URL.rstrip('/')}/v1/models/{model}:embeddings",
    ]
    payloads = [{"input": text}, {"text": text}, {"inputs": [text]}]

    for url in candidates:
        for payload in payloads:
            resp = _post(url, payload)
            if resp is None or resp.status_code != 200:
                continue
            try:
                data = resp.json()
            except Exception:
                continue

            # common shapes
            if isinstance(data, dict):
                if "embedding" in data and isinstance(data["embedding"], list):
                    return np.array(data["embedding"], dtype=float)
                if "embeddings" in data and isinstance(data["embeddings"], list) and len(data["embeddings"]) > 0:
                    return np.array(data["embeddings"][0], dtype=float)
                if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    first = data["data"][0]
                    if isinstance(first, dict) and "embedding" in first:
                        return np.array(first["embedding"], dtype=float)

    return None


def completion(prompt: str, max_tokens: int = 256) -> Optional[str]:
    """Return completion text or None on failure.

    Tries a few common generate endpoints and response shapes.
    """
    if not GEMINI_API_KEY or not GEMINI_BASE_URL:
        return None

    model = TEXT_MODEL or "text-model"
    candidates = [
        f"{GEMINI_BASE_URL.rstrip('/')}/v1/models/{model}:generate",
        f"{GEMINI_BASE_URL.rstrip('/')}/v1/models/{model}:predict",
        f"{GEMINI_BASE_URL.rstrip('/')}/v1/models/{model}:complete",
    ]

    payloads = [
        {"prompt": prompt, "max_output_tokens": max_tokens},
        {"input": prompt, "max_tokens": max_tokens},
        {"text": prompt, "max_tokens": max_tokens},
    ]

    for url in candidates:
        for payload in payloads:
            resp = _post(url, payload, timeout=max(10.0, float(os.environ.get("GEMINI_REQUEST_TIMEOUT", "10.0"))))
            if resp is None or resp.status_code != 200:
                continue
            try:
                data = resp.json()
            except Exception:
                # try plain text
                if resp.text:
                    return resp.text.strip()
                continue

            # try several common response shapes
            if isinstance(data, dict):
                # Google-style: {'candidates': [{'content': '...'}]} or {'candidates': [{'output': '...'}]}
                if "candidates" in data and isinstance(data["candidates"], list) and len(data["candidates"]) > 0:
                    first = data["candidates"][0]
                    if isinstance(first, dict):
                        for key in ("content", "output", "text", "response"):
                            if key in first and isinstance(first[key], str):
                                return first[key]
                # OpenAI-like: {'choices': [{'text': '...'}]}
                if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
                    ch = data["choices"][0]
                    if isinstance(ch, dict) and "text" in ch:
                        return ch["text"]
                # simple fields
                for key in ("text", "response", "output"):
                    if key in data and isinstance(data[key], str):
                        return data[key]

            # fallback to raw text
            if resp.text:
                return resp.text.strip()

    return None
