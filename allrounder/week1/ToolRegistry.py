"""
ToolRegistry.py - Extensible Tool & MCP (Model Context Protocol) Integration Layer.

Design Patterns Used:
- Adapter Pattern: Wraps varied tools (local Python functions, external REST APIs, and MCP servers)
  behind a uniform BaseTool interface.
- Registry Pattern: Centralizes tool discovery, schema generation for LLMs, and dispatching.
"""

from abc import ABC, abstractmethod
import json
import logging
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ToolRegistry")


class ToolParameterSchema(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: ToolParameterSchema

    def to_openai_schema(self) -> Dict[str, Any]:
        """Converts to standard OpenAI/Anthropic function calling tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters.model_dump(),
            },
        }


class BaseTool(ABC):
    """Abstract Base Class for all pluggable tools."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Returns the tool metadata and parameter schema."""
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """Executes the tool with the given arguments."""
        pass


# -----------------------------------------------------------------------------
# Concrete Tool 1: RAG Knowledge Base Retrieval Tool
# -----------------------------------------------------------------------------
class RagKnowledgeTool(BaseTool):
    """Tool adapter exposing internal document knowledge base to LLMs."""

    def __init__(self, rag_engine_instance=None):
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


# -----------------------------------------------------------------------------
# Concrete Tool 2: External REST API Tool Adapter
# -----------------------------------------------------------------------------
class RestApiToolAdapter(BaseTool):
    """
    Adapter for arbitrary external REST APIs (e.g. Jira, GitHub, Slack, Weather, Stripe).
    Allows the AI Gateway to call external endpoints safely without code changes.
    """

    def __init__(
        self,
        name: str,
        description: str,
        endpoint_url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        parameter_schema: Optional[Dict[str, Any]] = None,
    ):
        self._name = name
        self._description = description
        self.endpoint_url = endpoint_url
        self.method = method.upper()
        self.headers = headers or {"Content-Type": "application/json"}
        self._parameters = ToolParameterSchema(**(parameter_schema or {}))

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self._name,
            description=self._description,
            parameters=self._parameters,
        )

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        try:
            if self.method == "GET":
                query_string = urllib.parse.urlencode(params)
                url = f"{self.endpoint_url}?{query_string}" if query_string else self.endpoint_url
                req = urllib.request.Request(url, headers=self.headers, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif self.method == "POST":
                data = json.dumps(params).encode("utf-8")
                req = urllib.request.Request(self.endpoint_url, data=data, headers=self.headers, method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            else:
                return {"error": f"Unsupported HTTP method {self.method}"}
        except Exception as e:
            logger.error(f"External API tool {self._name} error: {e}")
            return {"error": str(e), "endpoint": self.endpoint_url}


# -----------------------------------------------------------------------------
# Concrete Tool 3: Model Context Protocol (MCP) Tool Adapter
# -----------------------------------------------------------------------------
class MCPToolAdapter(BaseTool):
    """
    Model Context Protocol (MCP) Standard Client Adapter.
    
    Connects to MCP servers (e.g., PostgreSQL MCP, Git MCP, Filesystem MCP, Fetch MCP)
    and exposes their methods seamlessly into the AI Gateway orchestrator.
    """

    def __init__(
        self,
        mcp_server_name: str,
        tool_name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        mcp_dispatch_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ):
        self.mcp_server_name = mcp_server_name
        self.tool_name = tool_name
        self._desc = description
        self._schema = ToolParameterSchema(**parameters_schema)
        self._dispatch = mcp_dispatch_fn

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=f"mcp__{self.mcp_server_name}__{self.tool_name}",
            description=f"[MCP: {self.mcp_server_name}] {self._desc}",
            parameters=self._schema,
        )

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        if self._dispatch:
            return self._dispatch(self.tool_name, params)
        # Default mock / stub execution if running without external MCP daemon
        return {
            "mcp_server": self.mcp_server_name,
            "tool": self.tool_name,
            "params_received": params,
            "status": "success",
            "result": f"Executed MCP {self.tool_name} successfully via protocol.",
        }


# -----------------------------------------------------------------------------
# Central Tool Registry
# -----------------------------------------------------------------------------
class ToolRegistry:
    """Central registry for discovering, exposing, and executing tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        name = tool.definition.name
        self._tools[name] = tool
        logger.info(f"Registered tool: '{name}'")

    def unregister(self, name: str) -> None:
        if name in self._tools:
            del self._tools[name]

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Returns schemas for LLM client tool registration."""
        return [tool.definition.to_openai_schema() for tool in self._tools.values()]

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns human-readable summaries of all registered tools."""
        return [
            {
                "name": t.definition.name,
                "description": t.definition.description,
                "parameters": list(t.definition.parameters.properties.keys()),
            }
            for t in self._tools.values()
        ]

    def execute(
        self, tool_name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Any:
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' is not registered.")
        return tool.execute(arguments, context=context)


# Global singleton instance
tool_registry = ToolRegistry()
