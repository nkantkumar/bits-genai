"""Request and response models for the /search endpoint.
Pydantic enforces type safety at the API boundary - same pattern as Module 0.
"""
from __future__ import annotations
from typing import List

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    k: int = Field(default=3, ge=1, le=20)


class SearchResult(BaseModel):
    score: float
    source: str
    section: str
    text: str


class SearchResponse(BaseModel):
    results: List[SearchResult]
