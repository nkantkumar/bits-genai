"""Week 1 pipeline: ingest the Daily Planet archive, chunk it, save chunks.jsonl.

Run it:  python build_chunks.py
Output:  chunks.jsonl, the embedding-ready chunks we will turn into vectors in Week 2.
"""
import json

from rag.ingest import ingest_folder
from rag.chunk import chunk_documents, count_tokens


def main():
    docs = ingest_folder("data")
    print(f"Ingested {len(docs)} documents from the archive:")
    for doc in docs:
        print(f"  - {doc.metadata.get('source', '?'):32} "
              f"{count_tokens(doc.text):>5} tokens  "
              f"[{doc.metadata.get('section', '?')}]")

    chunks = chunk_documents(docs, chunk_size=400, chunk_overlap=50)
    print(f"\nSplit into {len(chunks)} chunks (size=400 tokens, overlap=50).")

    with open("chunks.jsonl", "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps({"text": chunk.text, "metadata": chunk.metadata}) + "\n")
    print("Saved chunks.jsonl - ready for embeddings in Week 2.")


if __name__ == "__main__":
    main()
