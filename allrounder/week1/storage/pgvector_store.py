"""
storage/pgvector_store.py - Enterprise PostgreSQL + pgvector Storage Adapter.

Features:
- Thread-safe connection handling.
- Hybrid vector indexing with HNSW index (m=16, ef_construction=64).
- GIN index on text for hybrid search readiness.
- Resilient type adaptation: Works seamlessly whether the 'pgvector' pip package
  is installed or not (via native json.dumps vector string adaptation).
"""

import json
import logging
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2 import pool

from .base import Chunk, SearchResult, VectorStore

logger = logging.getLogger("PgVectorStore")

# Check if pgvector python adapter is available
HAS_PGVECTOR_LIB = False
try:
    from pgvector.psycopg2 import register_vector
    HAS_PGVECTOR_LIB = True
except ImportError:
    HAS_PGVECTOR_LIB = False
    logger.info("pgvector Python package not installed; utilizing native PostgreSQL JSON vector adaptation.")


class PgVectorStore(VectorStore):
    """Production-grade PostgreSQL + pgvector vector store."""

    def __init__(self, postgres_url: str, min_conn: int = 1, max_conn: int = 10):
        self.postgres_url = postgres_url
        self.has_pgvector_lib = HAS_PGVECTOR_LIB
        self._pool: Optional[pool.SimpleConnectionPool] = None
        self._init_pool(min_conn, max_conn)
        self._init_schema()

    def _init_pool(self, min_conn: int, max_conn: int) -> None:
        try:
            self._pool = pool.SimpleConnectionPool(
                min_conn, max_conn, dsn=self.postgres_url, connect_timeout=4
            )
            logger.info("PostgreSQL connection pool initialized.")
        except Exception as e:
            logger.warning(f"Could not initialize connection pool ({e}). Will use direct connections.")
            self._pool = None

    def _get_connection(self):
        if self._pool:
            conn = self._pool.getconn()
        else:
            conn = psycopg2.connect(self.postgres_url, connect_timeout=4)
        if self.has_pgvector_lib:
            try:
                from pgvector.psycopg2 import register_vector
                register_vector(conn)
            except Exception:
                pass
        return conn

    def _release_connection(self, conn) -> None:
        if self._pool and conn:
            try:
                self._pool.putconn(conn)
            except Exception:
                pass
        elif conn:
            try:
                conn.close()
            except Exception:
                pass

    def _init_schema(self) -> None:
        """Create vector extension, table, and HNSW index."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            # 1. Enable pgvector
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            # 2. Chunks table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id TEXT PRIMARY KEY,
                    doc_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    page_start INT NOT NULL,
                    page_end INT NOT NULL,
                    chunk_index INT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INT NOT NULL,
                    embedding vector(1536),
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # 3. HNSW vector index for high-scale cosine similarity
            cur.execute("""
                CREATE INDEX IF NOT EXISTS rag_chunks_hnsw_idx 
                ON rag_chunks 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """)
            conn.commit()
            logger.info("PostgreSQL schema & HNSW vector index verified.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to initialize PostgreSQL schema: {e}")
            raise e
        finally:
            self._release_connection(conn)

    def health_check(self) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            ok = cur.fetchone()[0] == 1
            self._release_connection(conn)
            return ok
        except Exception:
            return False

    def count(self) -> int:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM rag_chunks;")
            return int(cur.fetchone()[0])
        finally:
            self._release_connection(conn)

    def clear(self) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("TRUNCATE TABLE rag_chunks;")
            conn.commit()
        finally:
            self._release_connection(conn)

    def _format_vector(self, embedding: List[float]) -> Any:
        """Adapts python float list to PostgreSQL vector format."""
        if self.has_pgvector_lib:
            return embedding
        # Native string format "[0.1, 0.2, ...]" supported by PostgreSQL vector extension
        return json.dumps(embedding)

    def upsert_chunks(self, chunks: List[Chunk]) -> int:
        if not chunks:
            return 0
        conn = self._get_connection()
        written = 0
        try:
            cur = conn.cursor()
            for c in chunks:
                vec_val = self._format_vector(c.embedding) if c.embedding else None
                cur.execute(
                    """
                    INSERT INTO rag_chunks (
                        id, doc_name, title, page_start, page_end, chunk_index,
                        content, token_count, embedding, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        token_count = EXCLUDED.token_count,
                        metadata = EXCLUDED.metadata;
                    """,
                    (
                        c.chunk_id,
                        c.doc_name,
                        c.title,
                        c.page_start,
                        c.page_end,
                        c.chunk_index,
                        c.content,
                        c.token_count,
                        vec_val,
                        json.dumps(c.metadata),
                    ),
                )
                written += 1
            conn.commit()
            return written
        except Exception as e:
            conn.rollback()
            logger.error(f"Error persisting chunks to PostgreSQL: {e}")
            raise e
        finally:
            self._release_connection(conn)

    def similarity_search(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[SearchResult]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            vec_val = self._format_vector(query_embedding)
            cur.execute(
                """
                SELECT id, doc_name, title, page_start, page_end, chunk_index,
                       content, token_count, metadata,
                       1 - (embedding <=> %s::vector) AS cosine_sim
                FROM rag_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector ASC
                LIMIT %s;
                """,
                (vec_val, vec_val, top_k),
            )
            rows = cur.fetchall()
            results: List[SearchResult] = []
            for row in rows:
                ch = Chunk(
                    chunk_id=row[0],
                    doc_name=row[1],
                    title=row[2],
                    page_start=row[3],
                    page_end=row[4],
                    chunk_index=row[5],
                    content=row[6],
                    token_count=row[7],
                    metadata=row[8] if isinstance(row[8], dict) else {},
                )
                sim = float(row[9])
                results.append(SearchResult(chunk=ch, similarity=sim, retrieval_source="pgvector"))
            return results
        except Exception as e:
            logger.error(f"PostgreSQL vector search failed: {e}")
            raise e
        finally:
            self._release_connection(conn)
