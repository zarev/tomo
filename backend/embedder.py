"""Deterministic lightweight embedder for PoC.

Generates a fixed-size vector (EMBED_DIM) from input text using repeated SHA-256
hashing. This is NOT a semantic embedder—it's a deterministic placeholder so the
PoC can exercise pgvector storage and nearest-neighbor queries locally without
downloading large embedding models.
"""
import hashlib
from typing import List

import numpy as np

EMBED_DIM = 64


def text_to_embedding(text: str) -> np.ndarray:
    """Return a deterministic embedding vector for `text` with shape (EMBED_DIM,).

    The values are in roughly [-0.5, 0.5].
    """
    if not text:
        text = ""
    state = hashlib.sha256(text.encode("utf-8")).digest()
    out: List[float] = []
    while len(out) < EMBED_DIM:
        state = hashlib.sha256(state).digest()
        # take 4-bytes at a time -> uint32 -> normalized float
        for i in range(0, len(state), 4):
            if len(out) >= EMBED_DIM:
                break
            chunk = state[i : i + 4]
            val = int.from_bytes(chunk, "big", signed=False)
            out.append((val % 10000) / 10000.0 - 0.5)

    return np.array(out, dtype=float)


def vec_to_pgvector_literal(vec: np.ndarray) -> str:
    """Format numpy vector as a pgvector literal string: '[v1,v2,...]'"""
    return "[" + ",".join(f"{float(x):.6f}" for x in vec.tolist()) + "]"
