"""Query phase (online): embed a question and find the closest chunks by meaning.

Run it:  python search.py "how is the new arena being paid for?"
"""
import sys

from rag.embed import embed_query
from rag.vector_store import FaissStore


def main():
    query = " ".join(sys.argv[1:]) or "How is the new arena being paid for?"
    store = FaissStore.load("index.faiss")

    query_vector = embed_query(query)
    print(f'Query: "{query}"\n')
    for score, chunk in store.search(query_vector, k=3):
        meta = chunk["metadata"]
        print(f"[{score:.3f}] {meta.get('source')}  ({meta.get('section')})")
        print(f"        {chunk['text'][:100].strip()}...\n")


if __name__ == "__main__":
    main()
