"""Retrieval — per-persona knowledge-base search.

The Embedder protocol keeps the pipeline model-agnostic:
- SentenceTransformerEmbedder: production (local, free, no API).
- TfEmbedder: deterministic token-overlap vectors — tests and a no-model
  fallback. Retrieval logic (cosine, top-k, threshold) is identical for both.

Below-threshold queries return [] — callers must render "no knowledge-base
match" explicitly, never let the LLM guess.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class ChunkHit:
    title: str | None
    source: str
    content: str
    score: float


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...


class TfEmbedder:
    """Deterministic term-frequency hashing vectors, L2-normalized.

    Deterministic across processes (blake2b, not built-in hash which is
    salted per run). Semantic quality is limited — that's what the real
    embedder is for; this one keeps tests hermetic and provides a
    dependency-free fallback.

    Similarity scores sit much lower than semantic embeddings, so it
    carries its own threshold (retrieve()'s 0.7 default is tuned for
    sentence-transformer vectors).
    """

    THRESHOLD = 0.25

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for token in _TOKEN_RE.findall(text.lower()):
                digest = hashlib.blake2b(token.encode(), digest_size=4).hexdigest()
                idx = int(digest, 16) % self.dim
                vecs[i, idx] += 1.0
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms


class SentenceTransformerEmbedder:
    """Production embedder — local, free, no API key.

    Lazy import keeps the heavy torch/transformers dependency out of import
    time (only the modules that actually embed pay for it).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # heavy import

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True).astype(np.float32)


def encode_blob(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def decode_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def retrieve(
    conn,
    embedder: Embedder,
    persona: str,
    query: str,
    *,
    top_k: int = 4,
    threshold: float = 0.45,
) -> list[ChunkHit]:
    """Top-k chunks for one persona with similarity >= threshold, best first.

    Empty result = "no knowledge-base match" — callers must state that.

    Default threshold 0.45 is empirically calibrated for all-MiniLM-L6-v2 on
    this corpus (relevant hits 0.5–0.66, unrelated queries < 0.35). The
    plan's original 0.7 proved too strict for semantic embeddings — 0.7+
    means near-duplicates. TfEmbedder carries its own threshold (0.25).
    """
    qvec = embedder.embed([query])[0]
    rows = conn.execute(
        "SELECT title, source, content, embedding FROM kb_chunks WHERE persona = ?",
        (persona,),
    ).fetchall()
    scored: list[tuple[float, object]] = []
    for row in rows:
        if row["embedding"] is None:
            continue
        similarity = float(np.dot(qvec, decode_blob(row["embedding"])))
        if similarity >= threshold:
            scored.append((similarity, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        ChunkHit(
            title=row["title"],
            source=row["source"],
            content=row["content"],
            score=round(similarity, 4),
        )
        for similarity, row in scored[:top_k]
    ]
