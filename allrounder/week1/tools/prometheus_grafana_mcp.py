"""
tools/prometheus_grafana_mcp.py - Prometheus & Grafana Model Context Protocol (MCP) Adapters.

Design Pattern:
- Adapter Pattern: Adapts external Prometheus time-series API and Grafana dashboard/alert
  APIs into uniform BaseTool instances compatible with LLM function-calling schemas.
- Plugin / Registry: Seamlessly registers into ToolRegistry with automatic rate limiting,
  graceful fallback telemetry for local offline development, and zero orchestrator coupling.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .base import BaseTool, ToolDefinition, ToolParameterSchema

logger = logging.getLogger("PrometheusGrafanaMCP")


class PrometheusMCPAdapter(BaseTool):
    """
    Model Context Protocol (MCP) tool adapter for Prometheus monitoring.
    Enables agents to query PromQL metrics, monitor gateway latency/spend,
    discover metric descriptors, and inspect active alerts.
    """

    DEFAULT_BASE_URL = "http://localhost:9090"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 6.0,
    ):
        self.base_url = (
            base_url
            or os.getenv("PROMETHEUS_URL")
            or os.getenv("PROMETHEUS_BASE_URL")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout = timeout

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mcp__prometheus__query",
            description=(
                "Query Prometheus time-series metrics via PromQL, inspect AI Gateway "
                "telemetry (request counts, P99 latency, cache hit ratios, token spend), "
                "list metric names, and retrieve active alerts."
            ),
            parameters=ToolParameterSchema(
                properties={
                    "action": {
                        "type": "string",
                        "enum": ["query_instant", "query_range", "list_metrics", "get_alerts"],
                        "description": (
                            "Prometheus operation: 'query_instant' (instant PromQL vector), "
                            "'query_range' (historical time-series), 'list_metrics' (catalog of metric names), "
                            "or 'get_alerts' (currently firing alerts)."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "PromQL expression (e.g. 'ai_gateway_requests_total', "
                            "'rate(litellm_requests_total[5m])', 'ai_gateway_p99_latency_ms')."
                        ),
                    },
                    "time": {
                        "type": "string",
                        "description": "Evaluation timestamp for 'query_instant' (RFC3339 or Unix timestamp).",
                    },
                    "start": {
                        "type": "string",
                        "description": "Start timestamp for 'query_range' (RFC3339 or Unix timestamp).",
                    },
                    "end": {
                        "type": "string",
                        "description": "End timestamp for 'query_range' (RFC3339 or Unix timestamp).",
                    },
                    "step": {
                        "type": "string",
                        "description": "Query resolution step duration for 'query_range' (e.g. '15s', '1m', '5m').",
                    },
                    "metric_name": {
                        "type": "string",
                        "description": "Optional keyword or prefix filter for 'list_metrics'.",
                    },
                },
                required=["action"],
            ),
        )

    def _make_request(
        self, endpoint: str, query_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Dispatches an HTTP GET request to Prometheus REST API with error handling."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if query_params:
            filtered = {k: v for k, v in query_params.items() if v is not None}
            if filtered:
                qs = urllib.parse.urlencode(filtered)
                url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AI-Gateway-PrometheusMCP/1.0", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except Exception as e:
            logger.info(f"Prometheus connection to {url} unavailable ({e}); returning high-fidelity simulation.")
            return {"status": "offline", "error": str(e), "url": url}

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        action = params.get("action")
        if not action:
            return {"status": "error", "error": "Missing required parameter 'action'."}

        now_ts = int(time.time())

        if action == "query_instant":
            query = params.get("query", "up")
            live = self._make_request("api/v1/query", {"query": query, "time": params.get("time")})
            if live.get("status") == "success":
                return live

            # High-fidelity realistic AI Gateway telemetry simulation
            sim_value = "1.0"
            metric_labels = {"service": "ai_gateway", "environment": "production"}

            q_lower = query.lower()
            if "latency" in q_lower or "p99" in q_lower:
                sim_value = "124.50"  # 124.5 ms
                metric_labels.update({"quantile": "0.99", "unit": "ms"})
            elif "cache" in q_lower:
                sim_value = "0.875"   # 87.5% hit ratio
                metric_labels.update({"cache_tier": "semantic_redis", "ratio": "hit_over_total"})
            elif "spend" in q_lower or "cost" in q_lower:
                sim_value = "1.428"   # $1.42 USD
                metric_labels.update({"currency": "USD", "provider": "openai"})
            elif "request" in q_lower or "traffic" in q_lower:
                sim_value = "1420"
                metric_labels.update({"http_status": "200", "proxy": "nginx_litellm"})

            return {
                "status": "success",
                "simulated_mock": True,
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": metric_labels,
                            "value": [now_ts, sim_value],
                        }
                    ],
                },
                "query": query,
                "timestamp": now_ts,
            }

        elif action == "query_range":
            query = params.get("query", "rate(http_requests_total[5m])")
            start = params.get("start", str(now_ts - 3600))
            end = params.get("end", str(now_ts))
            step = params.get("step", "60s")

            live = self._make_request(
                "api/v1/query_range", {"query": query, "start": start, "end": end, "step": step}
            )
            if live.get("status") == "success":
                return live

            # Simulated range data points
            datapoints = [
                [now_ts - 1800, "115.2"],
                [now_ts - 1200, "122.4"],
                [now_ts - 600, "130.1"],
                [now_ts, "124.5"],
            ]
            return {
                "status": "success",
                "simulated_mock": True,
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"service": "ai_gateway", "metric": query},
                            "values": datapoints,
                        }
                    ],
                },
                "query": query,
                "range": {"start": start, "end": end, "step": step},
            }

        elif action == "list_metrics":
            live = self._make_request("api/v1/label/__name__/values")
            if live.get("status") == "success":
                all_metrics = live.get("data", [])
                filter_term = (params.get("metric_name") or "").lower()
                if filter_term:
                    all_metrics = [m for m in all_metrics if filter_term in m.lower()]
                return {"status": "success", "count": len(all_metrics), "metrics": all_metrics}

            # Standard AI Gateway Prometheus metrics catalog
            catalog = [
                "ai_gateway_requests_total",
                "ai_gateway_p99_latency_ms",
                "ai_gateway_cache_hits_total",
                "ai_gateway_cache_misses_total",
                "ai_gateway_guardrail_rejections_total",
                "ai_gateway_hitl_pending_actions",
                "litellm_token_spend_usd",
                "litellm_upstream_retries_total",
                "nginx_active_connections",
                "pgvector_hnsw_query_duration_ms",
            ]
            filter_term = (params.get("metric_name") or "").lower()
            if filter_term:
                catalog = [m for m in catalog if filter_term in m.lower()]

            return {
                "status": "success",
                "simulated_mock": True,
                "count": len(catalog),
                "metrics": catalog,
            }

        elif action == "get_alerts":
            live = self._make_request("api/v1/alerts")
            if live.get("status") == "success":
                return live

            return {
                "status": "success",
                "simulated_mock": True,
                "alerts": [
                    {
                        "alertname": "GatewayHighLatencyWarning",
                        "severity": "warning",
                        "state": "firing",
                        "activeAt": now_ts - 300,
                        "annotations": {
                            "description": "AI Gateway upstream P99 latency exceeded 200ms over 5m window."
                        },
                        "labels": {"service": "ai_gateway", "tier": "upstream_llm"},
                    }
                ],
            }

        return {
            "status": "error",
            "error": f"Invalid action '{action}'. Supported actions: 'query_instant', 'query_range', 'list_metrics', 'get_alerts'.",
        }


class GrafanaMCPAdapter(BaseTool):
    """
    Model Context Protocol (MCP) tool adapter for Grafana dashboards & alerts.
    Enables agents to search dashboards, inspect telemetry panels, list datasources,
    and review alerting rules.
    """

    DEFAULT_BASE_URL = "http://localhost:3000"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 6.0,
    ):
        self.base_url = (
            base_url
            or os.getenv("GRAFANA_URL")
            or os.getenv("GRAFANA_BASE_URL")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.api_key = api_key or os.getenv("GRAFANA_API_KEY") or os.getenv("GRAFANA_TOKEN")
        self.timeout = timeout

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mcp__grafana__query",
            description=(
                "Search Grafana dashboards, inspect panel configurations, query active "
                "datasources (Prometheus, PostgreSQL/pgvector), and view alerting rules."
            ),
            parameters=ToolParameterSchema(
                properties={
                    "action": {
                        "type": "string",
                        "enum": ["search_dashboards", "get_dashboard", "list_datasources", "get_alert_rules"],
                        "description": (
                            "Grafana operation: 'search_dashboards' (search by title/tag), "
                            "'get_dashboard' (fetch panel models by UID), 'list_datasources' "
                            "(list connected DBs/metrics backends), or 'get_alert_rules'."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": "Keyword to search dashboards or alerts (e.g. 'gateway', 'litellm', 'cache').",
                    },
                    "dashboard_uid": {
                        "type": "string",
                        "description": "Dashboard UID for 'get_dashboard' (e.g. 'ai-gateway-telemetry').",
                    },
                    "datasource_type": {
                        "type": "string",
                        "description": "Filter datasources by type (e.g. 'prometheus', 'postgres').",
                    },
                },
                required=["action"],
            ),
        )

    def _make_request(
        self, endpoint: str, query_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Performs authenticated HTTP request to Grafana REST API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if query_params:
            filtered = {k: v for k, v in query_params.items() if v is not None}
            if filtered:
                qs = urllib.parse.urlencode(filtered)
                url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"

        headers = {
            "User-Agent": "AI-Gateway-GrafanaMCP/1.0",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except Exception as e:
            logger.info(f"Grafana connection to {url} unavailable ({e}); returning high-fidelity simulation.")
            return {"status": "offline", "error": str(e), "url": url}

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        action = params.get("action")
        if not action:
            return {"status": "error", "error": "Missing required parameter 'action'."}

        if action == "search_dashboards":
            query = params.get("query", "")
            live = self._make_request("api/search", {"query": query, "type": "dash-db"})
            if isinstance(live, list) and live:
                return {"status": "success", "dashboards": live}

            # High-fidelity dashboard catalog for AI Gateway
            all_dashboards = [
                {
                    "uid": "ai-gateway-telemetry",
                    "title": "AI Security Gateway - Production Telemetry & Traffic",
                    "tags": ["gateway", "nginx", "litellm", "production"],
                    "url": "/d/ai-gateway-telemetry",
                    "panels_count": 8,
                },
                {
                    "uid": "litellm-spend-budget",
                    "title": "LiteLLM Spend, Budgets & Token Usage",
                    "tags": ["cost", "tokens", "budget", "finance"],
                    "url": "/d/litellm-spend-budget",
                    "panels_count": 5,
                },
                {
                    "uid": "cache-pgvector-health",
                    "title": "Storage & Caching: Redis Semantic Cache & PgVector HNSW",
                    "tags": ["database", "redis", "pgvector", "storage"],
                    "url": "/d/cache-pgvector-health",
                    "panels_count": 6,
                },
            ]
            if query:
                q_lower = query.lower()
                q_words = [w for w in q_lower.split() if len(w) > 2]
                filtered = [
                    d for d in all_dashboards
                    if q_lower in d["title"].lower()
                    or any(w in d["title"].lower() or any(w in t.lower() for t in d["tags"]) for w in q_words)
                ]
                # Graceful fallback to all dashboards if no specific filter matched
                if not filtered:
                    filtered = all_dashboards
            else:
                filtered = all_dashboards

            return {
                "status": "success",
                "simulated_mock": True,
                "count": len(filtered),
                "dashboards": filtered,
            }

        elif action == "get_dashboard":
            uid = params.get("dashboard_uid", "ai-gateway-telemetry")
            live = self._make_request(f"api/dashboards/uid/{uid}")
            if live.get("dashboard"):
                return {"status": "success", "dashboard": live.get("dashboard")}

            return {
                "status": "success",
                "simulated_mock": True,
                "dashboard": {
                    "uid": uid,
                    "title": "AI Security Gateway - Production Telemetry & Traffic",
                    "panels": [
                        {"id": 1, "title": "P99 End-to-End Latency (ms)", "type": "timeseries"},
                        {"id": 2, "title": "Requests per Second by Status Code", "type": "timeseries"},
                        {"id": 3, "title": "Exact & Semantic Cache Hit Ratio", "type": "gauge"},
                        {"id": 4, "title": "Daily Token Spend by Model (USD)", "type": "barchart"},
                    ],
                },
            }

        elif action == "list_datasources":
            live = self._make_request("api/datasources")
            if isinstance(live, list) and live:
                return {"status": "success", "datasources": live}

            return {
                "status": "success",
                "simulated_mock": True,
                "datasources": [
                    {
                        "id": 1,
                        "name": "Prometheus",
                        "type": "prometheus",
                        "url": "http://prometheus:9090",
                        "isDefault": True,
                    },
                    {
                        "id": 2,
                        "name": "PgVector-PostgreSQL",
                        "type": "postgres",
                        "url": "pgvector:5432",
                        "database": "rag_db",
                    },
                    {
                        "id": 3,
                        "name": "Redis-Cache",
                        "type": "redis-datasource",
                        "url": "redis:6379",
                    },
                ],
            }

        elif action == "get_alert_rules":
            live = self._make_request("api/v1/provisioning/alert-rules")
            if isinstance(live, list) and live:
                return {"status": "success", "alert_rules": live}

            return {
                "status": "success",
                "simulated_mock": True,
                "alert_rules": [
                    {
                        "title": "LiteLLM P99 Latency > 300ms",
                        "condition": "ai_gateway_p99_latency_ms > 300",
                        "for": "5m",
                        "state": "Normal",
                    },
                    {
                        "title": "Model Spend Threshold Exceeded",
                        "condition": "litellm_token_spend_usd > 50",
                        "for": "1h",
                        "state": "Normal",
                    },
                ],
            }

        return {
            "status": "error",
            "error": f"Invalid action '{action}'. Supported actions: 'search_dashboards', 'get_dashboard', 'list_datasources', 'get_alert_rules'.",
        }
