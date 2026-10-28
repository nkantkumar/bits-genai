"""
tools/base.py - Base abstractions for Tool & MCP Adapters.

Design Patterns Used:
- Adapter Pattern: Wraps heterogeneous tools (local functions, REST APIs, MCP servers)
  behind a uniform BaseTool interface.
- Registry Pattern: Centralizes tool discovery, schema generation, and execution.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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
    """Abstract Base Class for all pluggable tool adapters."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Returns tool metadata and JSON parameter schema."""
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """Executes the tool adapter with the supplied parameters."""
        pass
