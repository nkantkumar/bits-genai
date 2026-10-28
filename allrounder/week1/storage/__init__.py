"""
Storage module - Clean Vector Storage Abstraction (Ports & Adapters).
"""

from .base import Chunk, SearchResult, VectorStore
from .factory import VectorStoreFactory
from .in_memory_store import InMemoryVectorStore
from .pgvector_store import PgVectorStore

__all__ = [
    "Chunk",
    "SearchResult",
    "VectorStore",
    "VectorStoreFactory",
    "InMemoryVectorStore",
    "PgVectorStore",
]
