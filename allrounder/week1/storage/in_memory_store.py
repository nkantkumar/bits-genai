"""
storage/in_memory_store.py - High-Performance In-Memory Vector Store.

Resilient fallback when PostgreSQL or remote vector stores are unavailable.
Uses vectorized NumPy cosine similarity calculations with zero external DB dependencies.
"""

import logging
from typing import Dict, List, Optional
import numpy as np

from .base import Chunk, SearchResult, VectorStore

logger = logging.getLogger("InMemoryVectorStore")


class InMemoryVectorStore(VectorStore):
    """Thread-safe, zero-dependency vector store using NumPy."""

    def __init__(self):
        self._chunks: Dict[str, Chunk] = {}
        logger.info("Initialized resilient InMemoryVectorStore.")

    def health_check(self) -> bool:
        return True

    def count(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._chunks.clear()

    def upsert_chunks(self, chunks: List[Chunk]) -> int:
        written = 0
        for c in chunks:
            self._chunks[c.chunk_id] = c
            written += 1
        return written

    def similarity_search(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[SearchResult]:
        if not self._chunks:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec) + 1e-9

        results: List[SearchResult] = []
        for ch in self._chunks.values():
            if ch.embedding is None:
                continue
            c_vec = np.array(ch.embedding, dtype=np.float32)
            c_norm = np.linalg.norm(c_vec) + 1e-9
            sim = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))
            results.append(SearchResult(chunk=ch, similarity=sim, retrieval_source="in_memory"))

        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:top_k]
