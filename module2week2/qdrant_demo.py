"""The same search as FAISS - but in Qdrant, a real vector database.

Prereq: Qdrant running locally ->  docker compose up -d qdrant
Run it:  python qdrant_demo.py
"""
import json

from rag.embed import embed_texts, embed_query
from rag.qdrant_store import QdrantStore


def main():
    chunks = [json.loads(line) for line in open("chunks.jsonl", encoding="utf-8")]
    vectors = embed_texts([c["text"] for c in chunks])
    dim = len(vectors[0])

    store = QdrantStore(dim)
    store.add(vectors, chunks)
    print(f"Upserted {len(chunks)} chunks into Qdrant.\n")

    query = "How will the city pay for the new sports venue?"
    query_vector = embed_query(query)

    print(f'Query: "{query}"')
    for score, chunk in store.search(query_vector, k=3):
        meta = chunk["metadata"]
        print(f"  [{score:.3f}] {meta.get('source')} ({meta.get('section')})")

    print('\nSame query, but FILTERED to section="Weather" only:')
    for score, chunk in store.search(query_vector, k=3, section="Weather"):
        meta = chunk["metadata"]
        print(f"  [{score:.3f}] {meta.get('source')} ({meta.get('section')})")
    print("\n(The filter wins over similarity - the exact mechanism behind access control in Week 5.)")


if __name__ == "__main__":
    main()
