"""
RagEngine.py - Enterprise RAG with Semantic Chunking, RAG-Fusion,
Reciprocal Rank Fusion (RRF) Ranking, Deduplication, and PostgreSQL + pgvector.

Features:
1. Semantic Document Loading & Chunking:
   - Ingests PDFs from docs/ folder using pypdf.
   - Boundary-aware semantic chunking (sentences, headers, target 350-500 words with overlap).
2. Docker-based PostgreSQL + pgvector:
   - Stores 1536-dimensional vector embeddings (text-embedding-3-small).
   - In-database cosine similarity search with fallback in-memory cache for high availability.
3. RAG-Fusion:
   - Generates multi-perspective query expansions (conceptual, technical, tool-based).
4. Reciprocal Rank Fusion (RRF) Re-ranking:
   - Merges candidate rankings across all query variations: RRF(d) = sum(1 / (60 + rank)).
5. Smart Deduplication:
   - Removes exact & near-duplicate chunks across multi-query search results.
6. Grounded Synthesis:
   - Produces answers citing source documents and page numbers.
"""

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
import pypdf

# Ensure week1 is on sys.path
WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

# Load environment
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

logger = logging.getLogger("RagEngine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Database & Gateway Configuration
POSTGRES_URL = os.getenv("POSTGRES_RAG_URL", "postgresql://postgres:postgres@localhost:5433/rag_db")
BASE_URL = (
    os.getenv("NGINX_PROXY_URL")
    or os.getenv("LITELLM_PROXY_URL")
    or os.getenv("AI_GATEWAY_URL")
    or "http://localhost:8080/v1"
)
API_KEY = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
DOCS_DIR = WEEK1_DIR / "docs"

# Document semantic titles mapping for clean citations
DOC_TITLES = {
    "1792861009005.pdf": "Windows Privilege Escalation: SeTakeOwnershipPrivilege",
    "1792907264681.pdf": "AWS: Penetration Testing Lab Setup",
    "1792907573179.pdf": "PostgreSQL Penetration Testing",
    "1793025397798.pdf": "Comprehensive Guide on Wordlists (Kali, Dirb, Rockyou, SecLists)",
}


class Chunk:
    def __init__(
        self,
        chunk_id: str,
        doc_name: str,
        title: str,
        page_start: int,
        page_end: int,
        chunk_index: int,
        content: str,
        token_count: int,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.chunk_id = chunk_id
        self.doc_name = doc_name
        self.title = title
        self.page_start = page_start
        self.page_end = page_end
        self.chunk_index = chunk_index
        self.content = content
        self.token_count = token_count
        self.embedding = embedding
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_name": self.doc_name,
            "title": self.title,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


class RagEngine:
    def __init__(
        self,
        postgres_url: str = POSTGRES_URL,
        base_url: str = BASE_URL,
        api_key: Optional[str] = API_KEY,
        embedding_model: str = EMBEDDING_MODEL,
        docs_dir: Path = DOCS_DIR,
    ):
        self.postgres_url = postgres_url
        self.base_url = base_url
        self.api_key = api_key or "sk-dummy"
        self.embedding_model = embedding_model
        self.docs_dir = Path(docs_dir)

        # Clients
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.db_available = False
        self.in_memory_chunks: Dict[str, Chunk] = {}

        # Initialize pgvector storage
        self._init_database()

    def _init_database(self) -> None:
        """Connect to PostgreSQL, enable pgvector extension, and create tables."""
        try:
            import psycopg2
            conn = psycopg2.connect(self.postgres_url, connect_timeout=3)
            cur = conn.cursor()
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
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
            conn.commit()
            conn.close()
            self.db_available = True
            logger.info("PostgreSQL pgvector initialized successfully on port 5433.")
        except Exception as e:
            logger.warning(f"PostgreSQL pgvector unavailable ({e}). Operating in resilient in-memory mode.")
            self.db_available = False

    def get_embedding(self, text: str) -> List[float]:
        """Generate 1536-dim embedding vector via LiteLLM / OpenAI."""
        clean_text = text.replace("\n", " ").strip()
        try:
            resp = self.client.embeddings.create(
                model=self.embedding_model,
                input=clean_text[:8000],  # stay within context window
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation error via proxy: {e}. Trying direct OpenAI fallback.")
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

    # -------------------------------------------------------------------------
    # 1. Semantic Chunking
    # -------------------------------------------------------------------------
    def semantic_chunk_text(
        self,
        pages_text: List[Tuple[int, str]],
        doc_name: str,
        target_words: int = 350,
        overlap_sentences: int = 2,
    ) -> List[Chunk]:
        """
        Boundary-aware semantic chunking:
        - Segments text into semantic propositions/sentences.
        - Respects natural heading and topic changes.
        - Keeps overlapping context sentences between chunks.
        """
        title = DOC_TITLES.get(doc_name, doc_name.replace(".pdf", ""))
        chunks: List[Chunk] = []

        all_sentences: List[Tuple[int, str]] = []  # (page_num, sentence)

        sentence_end_regex = re.compile(r"(?<=[.!?])\s+|\n\n+")
        header_regex = re.compile(
            r"^(abstract|table of contents|chapter|\d+\.\d+|\b[A-Z\s]{4,}\b)",
            re.MULTILINE,
        )

        for page_num, p_text in pages_text:
            cleaned = p_text.strip()
            if not cleaned:
                continue
            raw_sents = sentence_end_regex.split(cleaned)
            for s in raw_sents:
                s_strip = s.strip()
                if len(s_strip) > 10:  # skip trivial artifacts
                    all_sentences.append((page_num, s_strip))

        if not all_sentences:
            return chunks

        current_sentences: List[str] = []
        current_word_count = 0
        start_page = all_sentences[0][0]
        end_page = start_page
        chunk_idx = 0

        for page_num, sent in all_sentences:
            words_in_sent = len(sent.split())
            is_header = bool(header_regex.search(sent))

            # Trigger chunk boundary if word budget reached or major section break encountered
            if (current_word_count + words_in_sent > target_words and current_word_count >= 150) or (
                is_header and current_word_count >= 180
            ):
                content = " ".join(current_sentences).strip()
                chunk_id = f"{doc_name}_{chunk_idx}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        doc_name=doc_name,
                        title=title,
                        page_start=start_page,
                        page_end=end_page,
                        chunk_index=chunk_idx,
                        content=content,
                        token_count=int(len(content.split()) * 1.3),
                    )
                )
                chunk_idx += 1

                # Sliding overlap: carry over the last N sentences for semantic continuity
                overlap = current_sentences[-overlap_sentences:] if len(current_sentences) >= overlap_sentences else []
                current_sentences = list(overlap)
                current_word_count = sum(len(s.split()) for s in current_sentences)
                start_page = page_num

            current_sentences.append(sent)
            current_word_count += words_in_sent
            end_page = page_num

        # Residual chunk
        if current_sentences:
            content = " ".join(current_sentences).strip()
            chunk_id = f"{doc_name}_{chunk_idx}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_name=doc_name,
                    title=title,
                    page_start=start_page,
                    page_end=end_page,
                    chunk_index=chunk_idx,
                    content=content,
                    token_count=int(len(content.split()) * 1.3),
                )
            )

        return chunks

    # -------------------------------------------------------------------------
    # 2. Ingestion & Indexing Pipeline
    # -------------------------------------------------------------------------
    def ingest_docs(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Parses all PDFs in the docs/ folder, chunks them semantically,
        generates vector embeddings, and persists them into PostgreSQL pgvector.
        """
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

            # Semantic chunking
            doc_chunks = self.semantic_chunk_text(pages_text, doc_name=doc_name)
            logger.info(f"Chunked {doc_name} ({len(reader.pages)} pages) -> {len(doc_chunks)} semantic chunks")

            # Generate embeddings in batches of 16
            contents = [c.content for c in doc_chunks]
            batch_size = 16
            for i in range(0, len(doc_chunks), batch_size):
                batch_chunks = doc_chunks[i : i + batch_size]
                batch_texts = contents[i : i + batch_size]
                embeddings = self.get_embeddings_batch(batch_texts)
                for chunk, emb in zip(batch_chunks, embeddings):
                    chunk.embedding = emb
                    self.in_memory_chunks[chunk.chunk_id] = chunk

            # Store in PostgreSQL pgvector if available
            if self.db_available:
                self._persist_chunks_to_postgres(doc_chunks)

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

    def _persist_chunks_to_postgres(self, chunks: List[Chunk]) -> None:
        """Upsert chunks with vector embeddings into PostgreSQL."""
        import psycopg2
        from pgvector.psycopg2 import register_vector

        conn = psycopg2.connect(self.postgres_url)
        register_vector(conn)
        cur = conn.cursor()

        for c in chunks:
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
                    c.embedding,
                    json.dumps(c.metadata),
                ),
            )
        conn.commit()
        conn.close()

    # -------------------------------------------------------------------------
    # 3. RAG-Fusion Query Generation
    # -------------------------------------------------------------------------
    def generate_fused_queries(self, prompt: str, num_queries: int = 3) -> List[str]:
        """
        RAG-Fusion: Prompts the LLM to generate diverse query formulations
        (e.g., conceptual, syntax/command-line, practical exploitation/defense).
        """
        fused = [prompt.strip()]
        sys_prompt = (
            "You are an AI search query optimization expert. Given a user question, generate "
            f"{num_queries} diverse search queries targeting a technical security knowledge base "
            "(Windows privilege escalation, AWS lab setup, PostgreSQL pentesting, and wordlists). "
            "Formulate variations from different technical angles (e.g. theoretical concept, "
            "specific commands/flags/tools, and step-by-step remediation). "
            "Reply with exactly one query per line, without numbering, bullets, or explanations."
        )

        try:
            r = self.client.chat.completions.create(
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

    # -------------------------------------------------------------------------
    # 4. Vector Search per Query
    # -------------------------------------------------------------------------
    def _search_vector(self, query_text: str, top_k: int = 5) -> List[Tuple[Chunk, float]]:
        """Vector similarity search against pgvector (or fallback in-memory)."""
        query_emb = self.get_embedding(query_text)

        if self.db_available:
            try:
                import psycopg2
                from pgvector.psycopg2 import register_vector

                conn = psycopg2.connect(self.postgres_url)
                register_vector(conn)
                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT id, doc_name, title, page_start, page_end, chunk_index,
                           content, token_count, metadata,
                           1 - (embedding <=> %s::vector) AS cosine_sim
                    FROM rag_chunks
                    ORDER BY embedding <=> %s::vector ASC
                    LIMIT %s;
                    """,
                    (query_emb, query_emb, top_k),
                )
                rows = cur.fetchall()
                conn.close()

                results = []
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
                    results.append((ch, sim))
                return results
            except Exception as e:
                logger.warning(f"PostgreSQL query failed ({e}), falling back to memory.")

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

    # -------------------------------------------------------------------------
    # 5. Reciprocal Rank Fusion (RRF) & Deduplication
    # -------------------------------------------------------------------------
    def fuse_and_rank(
        self, queries: List[str], top_k_per_query: int = 5, k_constant: int = 60
    ) -> Tuple[List[Tuple[Chunk, float]], int]:
        """
        Reciprocal Rank Fusion (RRF) over multi-query results:
        RRF(d) = sum(1 / (k_constant + rank(q, d)))
        Followed by smart semantic deduplication.
        """
        chunk_map: Dict[str, Chunk] = {}
        rrf_scores: Dict[str, float] = {}

        for q in queries:
            ranked_results = self._search_vector(q, top_k=top_k_per_query)
            for rank_idx, (chunk, _sim) in enumerate(ranked_results):
                rank = rank_idx + 1
                chunk_id = chunk.chunk_id
                chunk_map[chunk_id] = chunk
                rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (k_constant + rank))

        # Sort chunks by descending RRF score
        sorted_chunks = sorted(
            [(chunk_map[cid], rrf_scores[cid]) for cid in rrf_scores],
            key=lambda x: x[1],
            reverse=True,
        )

        # Smart Deduplication: Remove exact chunk duplicates and high text overlap (>75%)
        deduped: List[Tuple[Chunk, float]] = []
        initial_count = len(sorted_chunks)

        for chunk, score in sorted_chunks:
            # Check overlap against already admitted chunks
            c_words = set(chunk.content.lower().split())
            is_dup = False
            for admitted, _ in deduped:
                # Same doc and adjacent chunk or identical content prefix
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

    # -------------------------------------------------------------------------
    # 6. Grounded Answer Synthesis
    # -------------------------------------------------------------------------
    def query(
        self,
        prompt: str,
        model: str = "smart",
        fused_queries: Optional[List[str]] = None,
        max_context_chunks: int = 4,
    ) -> Dict[str, Any]:
        """
        Full RAG pipeline:
        1. RAG-Fusion query generation (if not provided).
        2. Vector retrieval across pgvector for all queries.
        3. Reciprocal Rank Fusion (RRF) ranking.
        4. Deduplication of candidate passages.
        5. Grounded synthesis with citations.
        """
        start_time = time.time()

        # Step 1: Fusion queries
        queries = fused_queries or self.generate_fused_queries(prompt, num_queries=3)

        # Step 2 & 3: Multi-query search + RRF Ranking + Deduplication
        ranked_chunks, dedup_count = self.fuse_and_rank(queries, top_k_per_query=5)
        top_chunks = ranked_chunks[:max_context_chunks]

        # Build context block
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
            context_blocks.append(
                f"Source {idx + 1} {citation_label}:\n{chunk.content}\n"
            )

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


# Global singleton instance
rag_engine = RagEngine()


if __name__ == "__main__":
    print("=" * 70)
    print(" Testing RagEngine with PostgreSQL + pgvector")
    print("=" * 70)
    ingest_result = rag_engine.ingest_docs()
    print("Ingestion result:", json.dumps(ingest_result, indent=2))

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
