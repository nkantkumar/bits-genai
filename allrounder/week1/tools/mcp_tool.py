"""
tools/mcp_tool.py - Model Context Protocol (MCP) tool adapter.
"""

import logging
from typing import Any, Dict, Optional
from .base import BaseTool, ToolDefinition, ToolParameterSchema

logger = logging.getLogger("MCPToolAdapter")


class MCPToolAdapter(BaseTool):
    """
    Adapter bridging standard Model Context Protocol (MCP) server endpoints
    into callable functions for LLM function calling schemas.
    """

    def __init__(
        self,
        mcp_server_name: str,
        tool_name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        mcp_client_transport: Optional[Any] = None,
    ):
        self.mcp_server_name = mcp_server_name
        self.tool_name = tool_name
        self._description = description
        self.parameters_schema = parameters_schema
        self.mcp_client_transport = mcp_client_transport

    @property
    def definition(self) -> ToolDefinition:
        unified_name = f"mcp__{self.mcp_server_name}__{self.tool_name}"
        return ToolDefinition(
            name=unified_name,
            description=f"[MCP: {self.mcp_server_name}] {self._description}",
            parameters=ToolParameterSchema(
                properties=self.parameters_schema.get("properties", {}),
                required=self.parameters_schema.get("required", []),
            ),
        )

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        logger.info(f"Dispatching to MCP Server [{self.mcp_server_name}]: tool={self.tool_name}, args={params}")
        if self.mcp_client_transport:
            return self.mcp_client_transport.call_tool(self.tool_name, params)

        # Standard simulated response for local/offline MCP testing
        return {
            "status": "success",
            "mcp_server": self.mcp_server_name,
            "tool": self.tool_name,
            "result": f"Executed MCP {self.tool_name} successfully",
            "parameters": params,
        }
