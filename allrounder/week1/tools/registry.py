"""
tools/registry.py - Centralized Tool & MCP Registry (Plugin / Registry Pattern).
"""

import logging
from typing import Any, Dict, List, Optional
from .base import BaseTool

logger = logging.getLogger("ToolRegistry")


class ToolRegistry:
    """Centralized Registry managing tool registration, schema export, and execution."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Registers a tool adapter."""
        name = tool.definition.name
        self._tools[name] = tool
        logger.info(f"Registered tool: '{name}'")

    def unregister(self, tool_name: str) -> None:
        if tool_name in self._tools:
            del self._tools[tool_name]

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        return self._tools.get(tool_name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns metadata list of all registered tools."""
        return [
            {
                "name": t.definition.name,
                "description": t.definition.description,
                "parameters": t.definition.parameters.model_dump(),
            }
            for t in self._tools.values()
        ]

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Exports all registered tools as OpenAI/LiteLLM function-calling schemas."""
        return [t.definition.to_openai_schema() for t in self._tools.values()]

    def execute(self, tool_name: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """Dispatches execution to the corresponding tool adapter."""
        tool = self.get_tool(tool_name)
        if not tool:
            raise KeyError(f"Tool '{tool_name}' is not registered.")
        return tool.execute(params, context=context)


def create_default_registry() -> ToolRegistry:
    """Creates registry with default out-of-the-box adapters (GitHub REST API, etc.)."""
    reg = ToolRegistry()
    try:
        from .github_tool import GitHubToolAdapter
        reg.register(GitHubToolAdapter())
    except Exception as e:
        logger.warning(f"Failed to auto-register default GitHub tool: {e}")
    return reg


# Global default registry instance
tool_registry = create_default_registry()
