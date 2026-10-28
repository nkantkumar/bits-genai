"""
allrounder.week1 - Production Enterprise AI Gateway Architecture.

Architectural Packages:
- guardrails: Chain of Responsibility & Interceptor pattern (Prompt Injection, PII Masking, Secret Leakage, Groundedness)
- caching: Cache-Aside pattern (Exact O(1) SHA-256 hash & Semantic Vector Cosine similarity)
- routing: Strategy pattern (Rule-based heuristics, LLM judge, and Cost cascading)
- orchestration: Finite State Machine (FSM) & Command pattern (Human-in-the-Loop gateway)
- tools: Adapter pattern & Plugin Registry (RAG knowledge tool, REST API adapter, MCP adapter)
- storage: Ports & Adapters (Hexagonal Architecture) & Factory Method (PostgreSQL pgvector & InMemory fallback)
- rag: Pipeline pattern (Boundary-aware Semantic Chunking, RAG-Fusion, RRF Re-ranking, Deduplication)
"""

from .guardrails import InputGuardrails, OutputGuardrails, input_guardrails, output_guardrails
from .caching import SemanticCache
from .routing import SmartRouter, smart_router
from .tools import (
    ToolRegistry,
    tool_registry,
    BaseTool,
    RagKnowledgeTool,
    RestApiToolAdapter,
    MCPToolAdapter,
    GitHubToolAdapter,
    GitHubApiTool,
    PrometheusMCPAdapter,
    GrafanaMCPAdapter,
)
from .orchestration import Orchestrator, orchestrator, ExecutionStrategy, RiskLevel
from .storage import VectorStore, VectorStoreFactory, PgVectorStore, InMemoryVectorStore, Chunk
from .rag import RagEngine, rag_engine

__all__ = [
    "InputGuardrails",
    "OutputGuardrails",
    "input_guardrails",
    "output_guardrails",
    "SemanticCache",
    "SmartRouter",
    "smart_router",
    "ToolRegistry",
    "tool_registry",
    "BaseTool",
    "RagKnowledgeTool",
    "RestApiToolAdapter",
    "MCPToolAdapter",
    "GitHubToolAdapter",
    "GitHubApiTool",
    "PrometheusMCPAdapter",
    "GrafanaMCPAdapter",
    "Orchestrator",
    "orchestrator",
    "ExecutionStrategy",
    "RiskLevel",
    "VectorStore",
    "VectorStoreFactory",
    "PgVectorStore",
    "InMemoryVectorStore",
    "Chunk",
    "RagEngine",
    "rag_engine",
]
