# Module 2 · Week 2: Embeddings & Vector Search

The second stage of "The Daily Planet AI Desk" RAG pipeline. You turn last week's clean, chunked
archive into vectors of meaning, then search it: first in FAISS (a local library), then in
Qdrant (a real vector database running in Docker).

## What you build
- `rag/embed.py`: a provider-agnostic OpenAI embeddings wrapper (`embed_texts`, `embed_query`).
- `rag/vector_store.py`: `FaissStore`, a tiny local vector store (cosine similarity via
  `IndexFlatIP` plus `normalize_L2`), with `save` and `load`.
- `rag/qdrant_store.py`: `QdrantStore`, the same search backed by a real vector database,
  with optional metadata filtering (for example, by `section`).
- `build_index.py`: the offline pipeline. Embed every chunk, save a searchable FAISS index.
- `search.py`: the online pipeline. Embed a question, return the top-k closest chunks.
- `qdrant_demo.py`: the same search in Qdrant, plus a metadata-filtered search.
- `app/`: a small FastAPI service (`models.py`, `services.py`, `main.py`) exposing `POST /search`
  over the FAISS index. The archive is now queryable over HTTP, not just from a Python script.
  This is the **same service** Week 4 later extends with `/ask`.

## Setup
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
Copy `.env.example` to `.env` and add your own OpenAI API key. This week **does** call an LLM
(the embedding model), so a real key is required.

## Run
```bash
python build_chunks.py            # from Week 1: ingest -> chunk -> chunks.jsonl
python build_index.py             # embed every chunk -> index.faiss
python search.py "How is the new arena being paid for?"
```
For the Qdrant demo, start the vector database first:
```bash
docker compose up -d qdrant
python qdrant_demo.py
```
For the API:
```bash
uvicorn app.main:app --port 8000
curl -X POST http://127.0.0.1:8000/search -H "Content-Type: application/json" \
     -d '{"query": "How is the new arena being paid for?", "k": 3}'
```

## Note
Embedding the entire curated archive costs a few cents with `text-embedding-3-small`. This is
the first week with a real, small API cost.

## The archive (`data/`)
The same Daily Planet corpus as Week 1: clean markdown articles plus one deliberately messy
HTML wire story.
