"""Chunking: split Documents into embedding-ready pieces that keep their metadata.

Stage 2 of the pipeline. We split each document into small, self-contained
chunks. Chunk size and overlap directly decide retrieval quality, so this is
one of the highest-leverage decisions in the whole system.
"""
from __future__ import annotations
from dataclasses import dataclass, field

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.ingest import Document

_ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    """Roughly how many tokens the embedding model will see for this text."""
    return len(_ENCODER.encode(text))


def naive_chunk(text, size=400):
    """A too-simple splitter: cut blindly every `size` characters. Splits mid-word."""
    return [text[i:i + size] for i in range(0, len(text), size)]


@dataclass
class Chunk:
    """One retrievable piece of a document, carrying its parent's metadata."""
    text: str
    metadata: dict = field(default_factory=dict)


def chunk_documents(docs, chunk_size=400, chunk_overlap=50):
    """Split each Document into overlapping, metadata-tagged chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=count_tokens,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for doc in docs:
        for i, piece in enumerate(splitter.split_text(doc.text)):
            meta = dict(doc.metadata)              # copy parent metadata onto the chunk
            meta["chunk_index"] = i
            meta["chunk_id"] = f"{meta.get('source', 'doc')}::{i}"
            chunks.append(Chunk(text=piece, metadata=meta))
    return chunks
