"""
rag/engine.py - Complete Enterprise RAG Pipeline Coordinator.

Connects:
- Chunker: Boundary-aware semantic chunking
- Storage: Ports & Adapters VectorStore (PostgreSQL pgvector / InMemory)
- Fusion: Multi-query expansion & Reciprocal Rank Fusion (RRF)
- Synthesizer: Grounded LLM response synthesis with citations
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
import pypdf

try:
    from ..storage import Chunk, PgVectorStore, VectorStoreFactory
    from .chunker import DOC_TITLES, SemanticChunker
    from .fusion import FusionRanker
except (ImportError, ValueError):
    from storage import Chunk, PgVectorStore, VectorStoreFactory
    from rag.chunker import DOC_TITLES, SemanticChunker
    from rag.fusion import FusionRanker

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv()

logger = logging.getLogger("RagEngine")

POSTGRES_URL = os.getenv("POSTGRES_RAG_URL", "postgresql://postgres:postgres@localhost:5433/rag_db")
BASE_URL = (
    os.getenv("NGINX_PROXY_URL")
    or os.getenv("LITELLM_PROXY_URL")
    or os.getenv("AI_GATEWAY_URL")
    or "http://localhost:8080/v1"
)
API_KEY = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


class RagEngine:
    """Enterprise RAG Engine implementing the Pipeline Pattern."""

    def __init__(
        self,
        postgres_url: str = POSTGRES_URL,
        base_url: str = BASE_URL,
        api_key: Optional[str] = API_KEY,
        embedding_model: str = EMBEDDING_MODEL,
        docs_dir: Path = DEFAULT_DOCS_DIR,
    ):
        self.postgres_url = postgres_url
        self.base_url = base_url
        self.api_key = api_key or "sk-dummy"
        self.embedding_model = embedding_model
        self.docs_dir = Path(docs_dir)

        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.chunker = SemanticChunker(target_words=350, overlap_sentences=2)
        self.in_memory_chunks: Dict[str, Chunk] = {}

        # Initialize storage via Factory Pattern
        self.vector_store = VectorStoreFactory.create(self.postgres_url)
        self.db_available = isinstance(self.vector_store, PgVectorStore)
        if self.db_available:
            logger.info("RagEngine attached to PostgreSQL + pgvector vector store.")
        else:
            logger.info("RagEngine operating in resilient in-memory mode.")

    def get_embedding(self, text: str) -> List[float]:
        """Generate 1536-dim embedding vector via LiteLLM / OpenAI."""
        clean_text = text.replace("\n", " ").strip()
        try:
            resp = self.client.embeddings.create(
                model=self.embedding_model,
                input=clean_text[:8000],
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding error via proxy: {e}. Trying direct fallback.")
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key and openai_key != self.api_key:
                direct_client = OpenAI(api_key=openai_key)
                resp = direct_client.embeddings.create(
                    model=self.embedding_model,
                    input=clean_text[:8000],
                )
                return resp.data[0].embedding
            raise e

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding generation."""
        cleaned = [t.replace("\n", " ").strip()[:8000] for t in texts]
        try:
            resp = self.client.embeddings.create(
                model=self.embedding_model,
                input=cleaned,
            )
            return [item.embedding for item in resp.data]
        except Exception as e:
            logger.warning(f"Batch embedding failed, falling back to sequential: {e}")
            return [self.get_embedding(t) for t in texts]

    def ingest_docs(self, force_reload: bool = False) -> Dict[str, Any]:
        """Parses all PDFs in docs/, chunks them, embeds them, and upserts into VectorStore."""
        start_time = time.time()
        if not self.docs_dir.exists():
            return {"status": "error", "message": f"Docs directory {self.docs_dir} not found"}

        pdf_files = sorted([f for f in self.docs_dir.iterdir() if f.suffix.lower() == ".pdf"])
        if not pdf_files:
            return {"status": "warning", "message": "No PDF documents found in docs/"}

        total_chunks_created = 0
        docs_processed: List[str] = []

        for pdf_path in pdf_files:
            doc_name = pdf_path.name
            reader = pypdf.PdfReader(str(pdf_path))
            pages_text = []
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages_text.append((idx + 1, text))

            doc_chunks = self.chunker.chunk_document(pages_text, doc_name=doc_name)
            logger.info(f"Chunked {doc_name} ({len(reader.pages)} pages) -> {len(doc_chunks)} chunks")

            contents = [c.content for c in doc_chunks]
            batch_size = 16
            for i in range(0, len(doc_chunks), batch_size):
                batch_chunks = doc_chunks[i : i + batch_size]
                batch_texts = contents[i : i + batch_size]
                embeddings = self.get_embeddings_batch(batch_texts)
                for chunk, emb in zip(batch_chunks, embeddings):
                    chunk.embedding = emb
                    self.in_memory_chunks[chunk.chunk_id] = chunk

            # Persist via VectorStore abstraction
            self.vector_store.upsert_chunks(doc_chunks)
            total_chunks_created += len(doc_chunks)
            docs_processed.append(doc_name)

        elapsed = round(time.time() - start_time, 2)
        return {
            "status": "success",
            "docs_processed": docs_processed,
            "total_chunks": total_chunks_created,
            "database": "postgresql+pgvector" if self.db_available else "in_memory",
            "elapsed_seconds": elapsed,
        }

    def _search_vector(self, query_text: str, top_k: int = 5) -> List[Tuple[Chunk, float]]:
        """Vector similarity search against VectorStore (or fallback in-memory)."""
        query_emb = self.get_embedding(query_text)
        try:
            results = self.vector_store.similarity_search(query_emb, top_k=top_k)
            if results:
                return [(r.chunk, r.similarity) for r in results]
        except Exception as e:
            logger.warning(f"VectorStore query failed ({e}), falling back to memory.")

        # In-memory cosine similarity fallback
        scored: List[Tuple[Chunk, float]] = []
        q_vec = np.array(query_emb, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec) + 1e-9

        for ch in self.in_memory_chunks.values():
            if ch.embedding is None:
                continue
            c_vec = np.array(ch.embedding, dtype=np.float32)
            sim = float(np.dot(q_vec, c_vec) / (q_norm * (np.linalg.norm(c_vec) + 1e-9)))
            scored.append((ch, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def generate_fused_queries(self, prompt: str, num_queries: int = 3) -> List[str]:
        return FusionRanker.generate_fused_queries(prompt, client=self.client, num_queries=num_queries)

    def fuse_and_rank(self, queries: List[str], top_k_per_query: int = 5) -> Tuple[List[Tuple[Chunk, float]], int]:
        return FusionRanker.fuse_and_rank(queries, self._search_vector, top_k_per_query=top_k_per_query)

    def query(
        self,
        prompt: str,
        model: str = "smart",
        fused_queries: Optional[List[str]] = None,
        max_context_chunks: int = 4,
    ) -> Dict[str, Any]:
        """Executes full RAG query pipeline with fusion, ranking, and grounded synthesis."""
        start_time = time.time()
        queries = fused_queries or self.generate_fused_queries(prompt, num_queries=3)
        ranked_chunks, dedup_count = self.fuse_and_rank(queries, top_k_per_query=5)
        top_chunks = ranked_chunks[:max_context_chunks]

        context_blocks = []
        citations = []
        for idx, (chunk, score) in enumerate(top_chunks):
            citation_label = f"[{chunk.title} | Page {chunk.page_start}]"
            citations.append({
                "doc_name": chunk.doc_name,
                "title": chunk.title,
                "pages": f"{chunk.page_start}-{chunk.page_end}",
                "rrf_score": round(score, 4),
                "preview": chunk.content[:160] + "...",
            })
            context_blocks.append(f"Source {idx + 1} {citation_label}:\n{chunk.content}\n")

        context_str = "\n".join(context_blocks)
        system_instruction = (
            "You are an enterprise technical AI assistant. Answer the user prompt accurately and "
            "thoroughly using ONLY the retrieved context documents below.\n"
            "Requirements:\n"
            "1. Ground every claim directly in the provided context.\n"
            "2. Cite your sources inline using [Document Title, Page X].\n"
            "3. If the context does not contain sufficient details to answer, state clearly what is missing.\n"
            "4. Format command examples and procedures in markdown code blocks."
        )

        user_content = f"CONTEXT:\n{context_str}\n\nUSER QUESTION: {prompt}"
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=800,
                temperature=0.2,
            )
            answer = resp.choices[0].message.content or ""
            model_used = resp.model or model
        except Exception as e:
            logger.error(f"Upstream generation failed: {e}")
            answer = f"[RAG SYNTHESIS ERROR]: {e}"
            model_used = "error"

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "answer": answer,
            "fused_queries": queries,
            "top_chunks": [c.to_dict() for c, _ in top_chunks],
            "citations": citations,
            "dedup_count": dedup_count,
            "latency_ms": elapsed_ms,
            "model_used": model_used,
        }


# Default singleton instance
rag_engine = RagEngine()
