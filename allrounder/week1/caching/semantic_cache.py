"""
caching/semantic_cache.py - Dual-Layer Exact & Semantic Vector Cache-Aside Engine.

Provides:
1. Layer 1 - Exact Prompt Cache:
   - O(1) hash lookup based on normalized prompt string and model.
   - 0 ms latency, 0 token cost.
2. Layer 2 - Semantic Vector Cache:
   - Vector embedding representation via `text-embedding-3-small`.
   - Cosine similarity matching: answers semantically equivalent questions
     even if phrased differently.
   - Configurable similarity threshold (default: 0.85).
"""

import hashlib
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from .base import BaseCache, CacheEntry

# Load environment
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv()


class SemanticCache(BaseCache):
    """Production Dual-Layer Exact & Semantic Vector Cache."""

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        embedding_model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.similarity_threshold = similarity_threshold
        self.embedding_model = embedding_model

        resolved_base_url = (
            base_url
            or os.getenv("NGINX_PROXY_URL")
            or os.getenv("LITELLM_PROXY_URL")
            or os.getenv("AI_GATEWAY_URL")
            or "http://localhost:4000/v1"
        )
        resolved_api_key = (
            api_key
            or os.getenv("LITELLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )

        self.client = OpenAI(base_url=resolved_base_url, api_key=resolved_api_key)

        # In-memory storage:
        # exact_cache: {hash(normalized_prompt + model): CacheEntry}
        self.exact_cache: Dict[str, CacheEntry] = {}
        # semantic_entries: List[CacheEntry]
        self.semantic_entries: List[CacheEntry] = []

        # Telemetry
        self.exact_hits: int = 0
        self.semantic_hits: int = 0
        self.misses: int = 0

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalizes text by trimming whitespace and converting to lowercase."""
        return " ".join(text.strip().lower().split())

    @staticmethod
    def _hash_key(prompt: str, model: str) -> str:
        """Generates SHA-256 hash key for exact matching."""
        content = f"{model}:{SemanticCache._normalize(prompt)}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generates a dense vector embedding using OpenAI or LiteLLM."""
        resp = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        vec = np.array(resp.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def get(self, prompt: str, model: str = "cheap") -> Tuple[Optional[str], str, float]:
        """
        Looks up prompt in cache using dual-layer check.
        Returns:
            (cached_response, hit_type, similarity_score)
        """
        # --- Layer 1: Exact Hash Match (O(1), 0ms) ---
        key = self._hash_key(prompt, model)
        if key in self.exact_cache:
            entry = self.exact_cache[key]
            entry.hit_count += 1
            self.exact_hits += 1
            return entry.response, "EXACT_MATCH", 1.0

        # --- Layer 2: Semantic Similarity Match ---
        if not self.semantic_entries:
            self.misses += 1
            return None, "CACHE_MISS", 0.0

        try:
            query_vec = self._get_embedding(prompt)
        except Exception:
            self.misses += 1
            return None, "CACHE_MISS", 0.0

        best_score = -1.0
        best_entry: Optional[CacheEntry] = None

        for entry in self.semantic_entries:
            if entry.model != model:
                continue
            sim = float(np.dot(query_vec, entry.embedding))
            if sim > best_score:
                best_score = sim
                best_entry = entry

        if best_entry and best_score >= self.similarity_threshold:
            best_entry.hit_count += 1
            self.semantic_hits += 1
            return best_entry.response, "SEMANTIC_MATCH", best_score

        self.misses += 1
        return None, "CACHE_MISS", max(best_score, 0.0)

    def set(self, prompt: str, response: str, model: str = "cheap") -> None:
        """Saves a prompt, its response, and embedding into the cache."""
        try:
            vec = self._get_embedding(prompt)
        except Exception:
            vec = np.zeros(1536, dtype=np.float32)

        entry = CacheEntry(
            prompt=prompt,
            response=response,
            model=model,
            embedding=vec,
            created_at=time.time(),
        )

        key = self._hash_key(prompt, model)
        self.exact_cache[key] = entry
        self.semantic_entries.append(entry)

    def clear(self) -> None:
        self.exact_cache.clear()
        self.semantic_entries.clear()
        self.exact_hits = 0
        self.semantic_hits = 0
        self.misses = 0

    def stats(self) -> Dict[str, Any]:
        total_queries = self.exact_hits + self.semantic_hits + self.misses
        hit_rate = (
            (self.exact_hits + self.semantic_hits) / total_queries if total_queries > 0 else 0.0
        )
        return {
            "total_entries": len(self.exact_cache),
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "misses": self.misses,
            "total_queries": total_queries,
            "hit_rate_pct": round(hit_rate * 100, 2),
            "similarity_threshold": self.similarity_threshold,
        }
