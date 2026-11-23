"""A tiny local vector store built on FAISS - for building intuition.

FAISS is a *library*: it holds vectors in memory and finds the nearest ones fast.
We use cosine similarity (inner product on normalized vectors) - the "same direction
= similar meaning" measure from the theory.
"""
from __future__ import annotations
import json
from pathlib import Path

import faiss
import numpy as np


class FaissStore:
    """Holds embedding vectors + their chunks, and searches by cosine similarity."""

    def __init__(self, dim):
        self.index = faiss.IndexFlatIP(dim)     # inner product; on normalized vectors = cosine
        self.chunks = []

    def add(self, vectors, chunks):
        arr = np.array(vectors, dtype="float32")
        faiss.normalize_L2(arr)                  # make every vector length 1 -> cosine
        self.index.add(arr)
        self.chunks.extend(chunks)

    def search(self, query_vector, k=3):
        q = np.array([query_vector], dtype="float32")
        faiss.normalize_L2(q)
        scores, idxs = self.index.search(q, k)
        results = []
        for score, i in zip(scores[0], idxs[0]):
            if i != -1:
                results.append((float(score), self.chunks[i]))
        return results

    def save(self, path="index.faiss"):
        faiss.write_index(self.index, path)
        Path(path + ".chunks.json").write_text(json.dumps(self.chunks), encoding="utf-8")

    @classmethod
    def load(cls, path="index.faiss"):
        store = cls(1)                            # dim is overwritten by the loaded index
        store.index = faiss.read_index(path)
        store.chunks = json.loads(Path(path + ".chunks.json").read_text(encoding="utf-8"))
        return store
