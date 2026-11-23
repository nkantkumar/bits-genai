"""
Daily Planet AI Desk API, a FastAPI application.
Routing layer only: receives requests, delegates to services, returns responses.
Same shape as the Module 0 service - semantic search is a new capability, not a new app.
"""
from fastapi import FastAPI
from .models import SearchRequest, SearchResponse
from .services import search

app = FastAPI(
    title="Daily Planet AI Desk",
    description="Semantic search over the newsroom archive - finds by meaning, not just spelling",
    version="1.0.0",
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/search", response_model=SearchResponse)
def search_endpoint(req: SearchRequest):
    results = search(req.query, req.k)
    return SearchResponse(results=results)
