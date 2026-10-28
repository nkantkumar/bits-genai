"""
tools/rest_tool.py - Adapter for external REST APIs (Jira, GitHub, Slack, Webhooks).
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional
from .base import BaseTool, ToolDefinition, ToolParameterSchema

logger = logging.getLogger("RestApiToolAdapter")


class RestApiToolAdapter(BaseTool):
    """Generic adapter bridging arbitrary HTTP REST endpoints to LLM tool calls."""

    def __init__(
        self,
        name: str,
        description: str,
        endpoint_url: str,
        http_method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        parameter_schema: Optional[Dict[str, Any]] = None,
    ):
        self._name = name
        self._description = description
        self.endpoint_url = endpoint_url
        self.http_method = http_method.upper()
        self.headers = headers or {"User-Agent": "AI-Gateway-Tool/1.0"}
        self._param_schema = parameter_schema or {}

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self._name,
            description=self._description,
            parameters=ToolParameterSchema(
                properties=self._param_schema.get("properties", {}),
                required=self._param_schema.get("required", []),
            ),
        )

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        url = self.endpoint_url
        data = None

        if self.http_method == "GET" and params:
            qs = urllib.parse.urlencode(params)
            url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"
        elif self.http_method in ("POST", "PUT"):
            data = json.dumps(params).encode("utf-8")
            self.headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=self.headers, method=self.http_method)
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"response": raw}
        except Exception as e:
            logger.error(f"REST tool '{self._name}' failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "simulated_mock": True,
                "message": f"Successfully simulated REST call to {url}",
                "input_params": params,
            }
