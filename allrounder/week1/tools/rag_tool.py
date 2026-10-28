"""
tools/rag_tool.py - Tool adapter exposing internal RAG knowledge base to LLMs.
"""

from typing import Any, Dict, Optional
from .base import BaseTool, ToolDefinition, ToolParameterSchema


class RagKnowledgeTool(BaseTool):
    """Tool adapter wrapping RAG document retrieval for function-calling LLMs."""

    def __init__(self, rag_engine_instance=None):
        self._engine = rag_engine_instance

    def attach_engine(self, rag_engine_instance) -> None:
        self._engine = rag_engine_instance

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_internal_knowledge_base",
            description=(
                "Search verified internal technical documentation, security runbooks, "
                "AWS lab setups, and PostgreSQL configurations."
            ),
            parameters=ToolParameterSchema(
                properties={
                    "query": {
                        "type": "string",
                        "description": "The search query to look up in documentation.",
                    },
                    "target_doc": {
                        "type": "string",
                        "description": "Optional specific document title to filter results.",
                    },
                },
                required=["query"],
            ),
        )

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        query_text = params.get("query", "")
        if self._engine:
            return self._engine.query(query_text)
        return {"status": "error", "message": "RagEngine not attached"}
