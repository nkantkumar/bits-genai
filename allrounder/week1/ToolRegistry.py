"""
ToolRegistry.py - Backward Compatibility Shim.
All implementations have been reorganized into the `tools/` package following
the Adapter and Plugin / Registry Design Patterns.
"""

import sys
from pathlib import Path

WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from tools import (
    BaseTool,
    GitHubApiTool,
    GitHubToolAdapter,
    GrafanaMCPAdapter,
    MCPToolAdapter,
    PrometheusMCPAdapter,
    RagKnowledgeTool,
    RestApiToolAdapter,
    ToolDefinition,
    ToolParameterSchema,
    ToolRegistry,
    tool_registry,
)

__all__ = [
    "BaseTool",
    "GitHubApiTool",
    "GitHubToolAdapter",
    "GrafanaMCPAdapter",
    "MCPToolAdapter",
    "PrometheusMCPAdapter",
    "RagKnowledgeTool",
    "RestApiToolAdapter",
    "ToolDefinition",
    "ToolParameterSchema",
    "ToolRegistry",
    "tool_registry",
]


if __name__ == "__main__":
    print("Registered tools:", [t["name"] for t in tool_registry.list_tools()])
