"""Business logic for the /search endpoint: load the FAISS index once at
startup, embed the query, and return the top-k chunks with sources + scores.
"""
from __future__ import annotations

from rag.embed import embed_query
from rag.vector_store import FaissStore

_store = None


def _get_store():
    global _store
    if _store is None:
        _store = FaissStore.load("index.faiss")
    return _store


def search(query: str, k: int = 3) -> list:
    store = _get_store()
    query_vector = embed_query(query)
    results = []
    for score, chunk in store.search(query_vector, k=k):
        meta = chunk["metadata"]
        results.append({
            "score": score,
            "source": meta.get("source", ""),
            "section": meta.get("section", ""),
            "text": chunk["text"][:200],
        })
    return results
