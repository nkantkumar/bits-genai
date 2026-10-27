"""
Production Semantic & Prompt Caching Engine (allrounder/week1)

Provides a dual-layer caching strategy:
1. Layer 1 - Exact Prompt Cache:
   - O(1) hash lookup based on normalized prompt string and model.
   - 0 ms latency, 0 token cost.
2. Layer 2 - Semantic Vector Cache:
   - Vector embedding representation via `text-embedding-3-small`.
   - Cosine similarity matching: answers semantically equivalent questions
     even if phrased completely differently (e.g. "capital of France" vs "what's France's capital?").
   - Configurable similarity threshold (default: 0.85).
"""

import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()


@dataclass
class CacheEntry:
    prompt: str
    response: str
    model: str
    embedding: np.ndarray
    created_at: float
    hit_count: int = 0


class SemanticCache:
    def __init__(
        self,
        similarity_threshold: float = 0.85,
        embedding_model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initializes the Semantic & Prompt Cache.

        Args:
            similarity_threshold: Cosine similarity threshold (0.0 to 1.0).
                                  >= 0.85 represents high semantic similarity.
            embedding_model: OpenAI embedding model name.
            base_url: Gateway or OpenAI base URL.
            api_key: Gateway or OpenAI API key.
        """
        self.similarity_threshold = similarity_threshold
        self.embedding_model = embedding_model

        # Client for generating embeddings (routed through LiteLLM or OpenAI)
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
        # 1. exact_cache: {hash(normalized_prompt + model): CacheEntry}
        self.exact_cache: Dict[str, CacheEntry] = {}
        # 2. semantic_entries: list of all CacheEntries for vector comparison
        self.entries: List[CacheEntry] = []

        # Metrics & telemetry
        self.total_queries = 0
        self.exact_hits = 0
        self.semantic_hits = 0
        self.misses = 0

    @staticmethod
    def _normalize_prompt(prompt: str) -> str:
        """Strip extraneous spaces and lowercase for exact matching."""
        return " ".join(prompt.strip().lower().split())

    @staticmethod
    def _compute_key(normalized_prompt: str, model: str) -> str:
        return hashlib.sha256(f"{model}:{normalized_prompt}".encode("utf-8")).hexdigest()

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generate and normalize vector embedding."""
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        vec = np.array(response.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def get(
        self, prompt: str, model: str = "cheap"
    ) -> Tuple[Optional[str], Optional[str], float]:
        """
        Look up a prompt in the cache.

        Returns:
            Tuple: (cached_response, hit_type, similarity_score)
            hit_type: "EXACT_MATCH", "SEMANTIC_MATCH", or None if cache miss.
        """
        self.total_queries += 1
        normalized = self._normalize_prompt(prompt)
        exact_key = self._compute_key(normalized, model)

        # -------------------------------------------------------------
        # 1. Check Layer 1: Exact Match Cache (O(1) Hash Lookup)
        # -------------------------------------------------------------
        if exact_key in self.exact_cache:
            entry = self.exact_cache[exact_key]
            entry.hit_count += 1
            self.exact_hits += 1
            return entry.response, "EXACT_MATCH", 1.0

        if not self.entries:
            self.misses += 1
            return None, None, 0.0

        # -------------------------------------------------------------
        # 2. Check Layer 2: Semantic Vector Similarity Cache
        # -------------------------------------------------------------
        query_embedding = self._get_embedding(prompt)

        # Filter entries matching the requested model
        matching_entries = [e for e in self.entries if e.model == model]
        if not matching_entries:
            self.misses += 1
            return None, None, 0.0

        # Stack candidate vectors into a matrix for fast batch cosine similarity
        matrix = np.vstack([e.embedding for e in matching_entries])
        # Dot product with normalized vectors gives cosine similarity directly
        similarities = np.dot(matrix, query_embedding)

        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= self.similarity_threshold:
            matched_entry = matching_entries[best_idx]
            matched_entry.hit_count += 1
            self.semantic_hits += 1

            # Also index under exact_cache for faster subsequent lookups
            self.exact_cache[exact_key] = matched_entry

            return matched_entry.response, "SEMANTIC_MATCH", best_score

        # Cache Miss
        self.misses += 1
        return None, None, best_score

    def set(self, prompt: str, response: str, model: str = "cheap") -> None:
        """Store a new prompt, embedding, and response in the cache."""
        normalized = self._normalize_prompt(prompt)
        exact_key = self._compute_key(normalized, model)

        embedding = self._get_embedding(prompt)
        entry = CacheEntry(
            prompt=prompt,
            response=response,
            model=model,
            embedding=embedding,
            created_at=time.time(),
        )

        self.exact_cache[exact_key] = entry
        self.entries.append(entry)

    def stats(self) -> Dict[str, any]:
        """Return cache hit-rate and performance metrics."""
        hits = self.exact_hits + self.semantic_hits
        hit_rate = (hits / self.total_queries * 100) if self.total_queries > 0 else 0.0
        return {
            "total_queries": self.total_queries,
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "misses": self.misses,
            "hit_rate_pct": round(hit_rate, 2),
            "total_cached_entries": len(self.entries),
            "similarity_threshold": self.similarity_threshold,
        }
