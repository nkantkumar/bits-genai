"""
storage/factory.py - Resilient Vector Store Factory.

Uses the Factory Method Pattern with automatic health probing and capability detection.
Guarantees that the application never crashes during startup due to missing vector dependencies
or transient database connectivity issues.
"""

import logging
import os
from .base import VectorStore
from .in_memory_store import InMemoryVectorStore

logger = logging.getLogger("VectorStoreFactory")


class VectorStoreFactory:
    """Factory to instantiate the appropriate VectorStore backend with resilient fallback."""

    @staticmethod
    def create(postgres_url: Optional[str] = None) -> VectorStore:
        url = postgres_url or os.getenv(
            "POSTGRES_RAG_URL", "postgresql://postgres:postgres@localhost:5433/rag_db"
        )
        try:
            from .pgvector_store import PgVectorStore
            store = PgVectorStore(url)
            if store.health_check():
                logger.info("Successfully connected to PostgreSQL + pgvector on port 5433.")
                return store
            else:
                logger.warning("PostgreSQL health check failed. Falling back to InMemoryVectorStore.")
        except Exception as e:
            logger.warning(
                f"PostgreSQL initialization failed ({e}). Operating in resilient in-memory mode."
            )

        return InMemoryVectorStore()
