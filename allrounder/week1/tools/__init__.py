"""
tools package - Pluggable Tools and MCP Integrations using Adapter & Registry Patterns.
"""

from .base import BaseTool, ToolDefinition, ToolParameterSchema
from .rag_tool import RagKnowledgeTool
from .rest_tool import RestApiToolAdapter
from .mcp_tool import MCPToolAdapter
from .registry import ToolRegistry, tool_registry

__all__ = [
    "BaseTool",
    "ToolDefinition",
    "ToolParameterSchema",
    "RagKnowledgeTool",
    "RestApiToolAdapter",
    "MCPToolAdapter",
    "ToolRegistry",
    "tool_registry",
]
