"""
RagEngine.py - Backward Compatibility Shim.
All implementations have been reorganized into the `rag/` package following
the Pipeline Design Pattern.
"""

import sys
from pathlib import Path

WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from rag import DOC_TITLES, FusionRanker, RagEngine, SemanticChunker, rag_engine

__all__ = [
    "DOC_TITLES",
    "SemanticChunker",
    "FusionRanker",
    "RagEngine",
    "rag_engine",
]

if __name__ == "__main__":
    print("=" * 70)
    print(" Testing RagEngine with PostgreSQL + pgvector")
    print("=" * 70)
    sample_query = "What is SeTakeOwnershipPrivilege and how is it exploited?"
    print(f"\nQuerying: '{sample_query}'")
    res = rag_engine.query(sample_query)
    print("\n--- Fused Queries Generated ---")
    for q in res["fused_queries"]:
        print(" *", q)
    print(f"\n--- Citations ({len(res['citations'])}) ---")
    for c in res["citations"]:
        print(f" * {c['title']} (Pages {c['pages']}) - RRF: {c['rrf_score']}")
    print(f"\n--- Answer (Latency: {res['latency_ms']}ms) ---")
    print(res["answer"][:400] + "...\n")
