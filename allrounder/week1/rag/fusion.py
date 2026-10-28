"""
rag/fusion.py - RAG-Fusion, Reciprocal Rank Fusion (RRF) Ranking, and Deduplication.

Design Patterns Used:
- Pipeline Pattern: Multi-perspective search expansion, rank merging, and candidate deduplication.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
try:
    from ..storage import Chunk
except (ImportError, ValueError):
    from storage import Chunk

logger = logging.getLogger("RagFusion")


class FusionRanker:
    """Handles query expansion, RRF re-ranking, and candidate deduplication."""

    @staticmethod
    def generate_fused_queries(
        prompt: str,
        client: Any = None,
        num_queries: int = 3,
    ) -> List[str]:
        """
        RAG-Fusion: Prompts LLM to generate diverse query formulations.
        """
        fused = [prompt.strip()]
        if not client:
            return fused

        sys_prompt = (
            "You are an AI search query optimization expert. Given a user question, generate "
            f"{num_queries} diverse search queries targeting a technical security knowledge base "
            "(Windows privilege escalation, AWS lab setup, PostgreSQL pentesting, and wordlists). "
            "Formulate variations from different technical angles (e.g. theoretical concept, "
            "specific commands/flags/tools, and step-by-step remediation). "
            "Reply with exactly one query per line, without numbering, bullets, or explanations."
        )

        try:
            r = client.chat.completions.create(
                model="cheap",
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=150,
                temperature=0.4,
            )
            raw = r.choices[0].message.content or ""
            lines = [line.strip().lstrip("0123456789.-* ") for line in raw.split("\n") if line.strip()]
            for line in lines[:num_queries]:
                if line and line.lower() != prompt.lower() and line not in fused:
                    fused.append(line)
        except Exception as e:
            logger.warning(f"RAG-Fusion query expansion failed: {e}. Using original prompt.")

        return fused

    @staticmethod
    def fuse_and_rank(
        queries: List[str],
        vector_search_fn: Callable[[str, int], List[Tuple[Chunk, float]]],
        top_k_per_query: int = 5,
        k_constant: int = 60,
    ) -> Tuple[List[Tuple[Chunk, float]], int]:
        """
        Reciprocal Rank Fusion (RRF) over multi-query results:
        RRF(d) = sum(1 / (k_constant + rank(q, d)))
        Followed by smart deduplication.
        """
        chunk_map: Dict[str, Chunk] = {}
        rrf_scores: Dict[str, float] = {}

        for q in queries:
            ranked_results = vector_search_fn(q, top_k_per_query)
            for rank_idx, (chunk, _sim) in enumerate(ranked_results):
                rank = rank_idx + 1
                chunk_id = chunk.chunk_id
                chunk_map[chunk_id] = chunk
                rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (k_constant + rank))

        sorted_chunks = sorted(
            [(chunk_map[cid], rrf_scores[cid]) for cid in rrf_scores],
            key=lambda x: x[1],
            reverse=True,
        )

        # Smart Deduplication: Remove exact duplicates and >75% content overlap
        deduped: List[Tuple[Chunk, float]] = []
        initial_count = len(sorted_chunks)

        for chunk, score in sorted_chunks:
            c_words = set(chunk.content.lower().split())
            is_dup = False
            for admitted, _ in deduped:
                if chunk.doc_name == admitted.doc_name and chunk.chunk_id == admitted.chunk_id:
                    is_dup = True
                    break
                a_words = set(admitted.content.lower().split())
                overlap = len(c_words.intersection(a_words)) / max(len(c_words), 1)
                if overlap > 0.75:
                    is_dup = True
                    break

            if not is_dup:
                deduped.append((chunk, score))

        dedup_count = initial_count - len(deduped)
        return deduped, dedup_count
