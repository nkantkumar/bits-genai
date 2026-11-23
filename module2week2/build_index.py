"""Indexing phase (offline): embed every chunk and save a searchable FAISS index.

Run it:  python build_index.py
Input:   chunks.jsonl  (from Week 1 - run `python build_chunks.py` first)
Output:  index.faiss (+ index.faiss.chunks.json)
"""
import json

from rag.embed import embed_texts
from rag.vector_store import FaissStore


def main():
    chunks = [json.loads(line) for line in open("chunks.jsonl", encoding="utf-8")]
    print(f"Loaded {len(chunks)} chunks. Embedding with OpenAI...")

    vectors = embed_texts([c["text"] for c in chunks])
    dim = len(vectors[0])
    print(f"Got {len(vectors)} vectors, each {dim} numbers long.")

    store = FaissStore(dim)
    store.add(vectors, chunks)
    store.save("index.faiss")
    print("Saved index.faiss - the archive is now searchable by meaning.")


if __name__ == "__main__":
    main()
