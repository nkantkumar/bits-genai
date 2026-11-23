"""Embeddings: turn text into vectors of meaning.

Provider-agnostic wrapper. We use OpenAI's `text-embedding-3-small`, but the same
pattern works with Anthropic, Cohere, or AWS Bedrock - swap the client, keep the code.

Golden rule: embed your QUERY with the SAME model you embedded your DOCUMENTS.
"""
from __future__ import annotations
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client = None
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()          # reads OPENAI_API_KEY from the environment
    return _client


def embed_texts(texts, model=None):
    """Embed a list of strings -> a list of vectors, in one API call."""
    response = _get_client().embeddings.create(model=model or DEFAULT_MODEL, input=texts)
    return [item.embedding for item in response.data]


def embed_query(text, model=None):
    """Embed a single query string -> one vector (same model as the documents!)."""
    return embed_texts([text], model=model)[0]
