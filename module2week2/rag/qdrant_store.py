"""The same semantic search, in Qdrant - a real vector database running in Docker.

FAISS was a library living inside our script. Qdrant is a *service*: it persists to
disk, filters by metadata, and answers many queries at once - the step from a
prototype to something you could build a product on. Here it runs locally in Docker.
"""
from __future__ import annotations
import os
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
)


class QdrantStore:
    """Stores vectors + metadata in Qdrant and searches by cosine similarity."""

    def __init__(self, dim, collection="daily_planet", url=None):
        self.client = QdrantClient(url=url or os.getenv("QDRANT_URL", "http://localhost:6333"))
        self.collection = collection
        if self.client.collection_exists(collection):
            self.client.delete_collection(collection)
        self.client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    def add(self, vectors, chunks):
        points = [
            PointStruct(id=str(uuid.uuid4()), vector=vector, payload=chunk)
            for vector, chunk in zip(vectors, chunks)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, query_vector, k=3, section=None):
        query_filter = None
        if section:                                  # metadata filtering - the Week 5 teaser
            query_filter = Filter(must=[
                FieldCondition(key="metadata.section", match=MatchValue(value=section))
            ])
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=k,
            query_filter=query_filter,
        )
        return [(hit.score, hit.payload) for hit in hits]
