"""
storage/base.py - Storage Abstraction Layer (Ports & Adapters Pattern).

Defines the core Chunk entity and the abstract VectorStore interface.
Enables pluggable storage backends (PostgreSQL + pgvector, In-Memory NumPy, Chroma, Qdrant)
without coupling core RAG or Orchestrator logic to database implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Chunk:
    chunk_id: str
    doc_name: str
    title: str
    page_start: int
    page_end: int
    chunk_index: int
    content: str
    token_count: int
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if "embedding" in d and d["embedding"] is not None:
            d["embedding_dim"] = len(d["embedding"])
            del d["embedding"]  # don't serialize huge raw vectors to frontend
        return d


@dataclass
class SearchResult:
    chunk: Chunk
    similarity: float
    retrieval_source: str = "vector"


class VectorStore(ABC):
    """
    Abstract Vector Storage Port.
    Implementations must be thread-safe and resilient to intermittent connection drops.
    """

    @abstractmethod
    def health_check(self) -> bool:
        """Returns True if the underlying storage engine is reachable and functional."""
        pass

    @abstractmethod
    def upsert_chunks(self, chunks: List[Chunk]) -> int:
        """Persists or updates chunks with their vector embeddings. Returns number of chunks written."""
        pass

    @abstractmethod
    def similarity_search(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[SearchResult]:
        """Performs dense vector cosine similarity search."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Returns the total number of stored chunks."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clears all stored chunks (used for testing and re-indexing)."""
        pass
