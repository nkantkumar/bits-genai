"""
AI Gateway Studio & HITL Orchestrator (allrounder/week1/app.py)

FastAPI application serving an interactive web UI and API that passes user queries
through the complete enterprise AI Gateway architecture:
1. Input Guardrails (PII Masking & Prompt Injection Blocking)
2. Semantic & Prompt Cache (Exact O(1) + Vector Cosine Similarity)
3. Model Complexity Router (Rules / LLM / Cascade)
4. Intelligent Orchestrator:
   - Evaluates whether query requires Direct LLM, Automated RAG, or Human-in-the-Loop (HITL) approval.
5. Best-Practice RAG Pipeline:
   - Boundary-aware Semantic Chunking
   - Docker-based PostgreSQL + pgvector vector store (host port 5433)
   - RAG-Fusion multi-perspective query expansion
   - Reciprocal Rank Fusion (RRF) Re-ranking
   - Smart Deduplication & Grounded Citations
6. Human-in-the-Loop (HITL) Approval Gateway:
   - Halts automated offensive/high-risk actions, allows interactive analyst approval, query modification, or rejection.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# Ensure week1 is on sys.path
WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

# Load environment
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

from guardrails import InputGuardrails, OutputGuardrails, PIIAction, GuardrailResult, output_guardrails
from tools import tool_registry
from caching import SemanticCache
from routing import SmartRouter, smart_router, CHEAP, SMART
from rag import rag_engine
from orchestration import orchestrator, ExecutionStrategy, RiskLevel

classify_by_rules = smart_router.classify_by_rules
classify_by_llm = smart_router.classify_by_llm
ask_with_cascade = smart_router.ask_with_cascade
from openai import OpenAI

logger = logging.getLogger("App")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

BASE_URL = (
    os.getenv("NGINX_PROXY_URL")
    or os.getenv("LITELLM_PROXY_URL")
    or os.getenv("AI_GATEWAY_URL")
    or "http://localhost:8080/v1"
)
API_KEY = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")

openai_client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
app_cache = SemanticCache(similarity_threshold=0.80)
app_guardrails = InputGuardrails(pii_action=PIIAction.MASK)

app = FastAPI(
    title="AI Gateway Studio with HITL Orchestrator",
    description="Enterprise Gateway: Guardrails, Cache, Smart Router, Orchestrator, pgvector RAG & Human-in-the-Loop",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Request & Response Models
# -----------------------------------------------------------------------------
class PromptRequest(BaseModel):
    prompt: str = Field(..., description="The user prompt to process")
    strategy: str = Field("rules", description="Routing strategy: rules, llm, or cascade")
    use_cache: bool = Field(True, description="Enable Exact & Semantic Caching")
    use_guardrails: bool = Field(True, description="Enable Input Guardrails")
    pii_action: str = Field("MASK", description="PII handling: MASK or BLOCK")
    use_orchestrator: bool = Field(True, description="Enable Intelligent Orchestrator & RAG")


class HitlDecisionRequest(BaseModel):
    action_id: str = Field(..., description="The pending action ID to resolve")
    decision: str = Field(..., description="Action decision: approve, modify, or reject")
    modified_query: Optional[str] = Field(None, description="Optional modified query if decision is modify")
    modified_queries: Optional[List[str]] = Field(None, description="Optional modified query list")


class ToolExecuteRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the registered tool to execute (e.g. 'github_api')")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the tool adapter")


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "gateway_url": BASE_URL,
        "cache_entries": len(app_cache.entries),
        "pgvector_connected": rag_engine.db_available,
        "indexed_chunks": len(rag_engine.in_memory_chunks),
        "pending_hitl_actions": len(orchestrator.list_pending_actions()),
        "registered_tools": [t["name"] for t in tool_registry.list_tools()],
    }


@app.get("/api/cache/stats")
def cache_stats() -> Dict[str, Any]:
    return app_cache.stats()


@app.post("/api/cache/clear")
def clear_cache() -> Dict[str, str]:
    app_cache.exact_cache.clear()
    app_cache.entries.clear()
    app_cache.total_queries = 0
    app_cache.exact_hits = 0
    app_cache.semantic_hits = 0
    app_cache.misses = 0
    return {"status": "cache_cleared"}


@app.get("/api/rag/stats")
def rag_stats() -> Dict[str, Any]:
    return {
        "database": "PostgreSQL 16 + pgvector (port 5433)" if rag_engine.db_available else "in_memory_fallback",
        "pgvector_active": rag_engine.db_available,
        "in_memory_cached_chunks": len(rag_engine.in_memory_chunks),
        "docs_directory": str(rag_engine.docs_dir),
    }


@app.post("/api/rag/ingest")
def rag_ingest() -> Dict[str, Any]:
    result = rag_engine.ingest_docs()
    return result


@app.get("/api/tools")
def list_tools() -> Dict[str, Any]:
    """Returns all registered tools, external REST adapters, and MCP tools."""
    return {
        "count": len(tool_registry.list_tools()),
        "tools": tool_registry.list_tools(),
    }


@app.post("/api/tools/execute")
def execute_tool_endpoint(req: ToolExecuteRequest) -> Dict[str, Any]:
    """Executes a registered tool adapter (e.g. GitHub REST API) and returns the output."""
    start_t = time.time()
    try:
        res = tool_registry.execute(req.tool_name, req.params)
        return {
            "success": True,
            "tool_name": req.tool_name,
            "params": req.params,
            "result": res,
            "elapsed_ms": round((time.time() - start_t) * 1000, 2),
        }
    except Exception as e:
        return {
            "success": False,
            "tool_name": req.tool_name,
            "params": req.params,
            "error": str(e),
            "elapsed_ms": round((time.time() - start_t) * 1000, 2),
        }


@app.get("/api/hitl/pending")
def list_hitl_pending() -> List[Dict[str, Any]]:
    return orchestrator.list_pending_actions()



def get_gateway_info(model_identifier: str) -> Dict[str, Any]:
    """Identifies whether the request flows through LiteLLM (Proxy) or directly to OpenAI."""
    is_litellm = "8080" in BASE_URL or "4000" in BASE_URL or "litellm" in BASE_URL.lower()
    if "8080" in BASE_URL:
        gateway_service = "LiteLLM (via Nginx Port 8080)"
        channel_label = "LiteLLM ➔ OpenAI"
    elif "4000" in BASE_URL:
        gateway_service = "LiteLLM Direct (Port 4000)"
        channel_label = "LiteLLM ➔ OpenAI"
    else:
        gateway_service = "Direct OpenAI API"
        channel_label = "Direct OpenAI"

    upstream_model = (
        "gpt-4o-mini" if "cheap" in str(model_identifier).lower()
        else ("gpt-4o" if "smart" in str(model_identifier).lower() else str(model_identifier))
    )
    return {
        "is_litellm": is_litellm,
        "gateway_service": gateway_service,
        "channel_label": channel_label,
        "endpoint": BASE_URL,
        "upstream_provider": "OpenAI",
        "upstream_model": upstream_model,
    }


@app.post("/api/hitl/respond")
def respond_hitl(req: HitlDecisionRequest) -> Dict[str, Any]:
    start_time = time.time()
    result = orchestrator.resolve_action(
        action_id=req.action_id,
        decision=req.decision,
        modified_query=req.modified_query,
        modified_queries=req.modified_queries,
    )
    result["total_elapsed_ms"] = round((time.time() - start_time) * 1000, 2)
    result["gateway"] = get_gateway_info(result.get("model_used", "cheap"))
    return result


@app.post("/api/chat")
def process_chat(req: PromptRequest) -> Dict[str, Any]:
    start_time = time.time()
    prompt = req.prompt.strip()

    guardrail_info: Optional[Dict[str, Any]] = None
    sanitized_prompt = prompt

    # Configure PII mode dynamically
    app_guardrails.pii_action = PIIAction.BLOCK if req.pii_action == "BLOCK" else PIIAction.MASK

    # -------------------------------------------------------------
    # Step 1: Input Guardrails Check
    # -------------------------------------------------------------
    if req.use_guardrails:
        g_result = app_guardrails.inspect(prompt)
        guardrail_info = {
            "passed": g_result.passed,
            "action": g_result.action,
            "violations": g_result.violations,
            "pii_entities": g_result.pii_entities,
            "risk_score": g_result.risk_score,
            "blocked_reason": g_result.blocked_reason,
        }

        if not g_result.passed:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "status": "blocked",
                "response": f"[GUARDRAIL BLOCKED]: {g_result.blocked_reason}",
                "model_used": "blocked_by_guardrail",
                "stage": "guardrails_blocked",
                "strategy": "NONE",
                "guardrail": guardrail_info,
                "cache": {"hit": False, "type": None, "similarity": 0.0},
                "gateway": get_gateway_info("none"),
                "latency_ms": round(elapsed * 1000, 2),
                "sanitized_prompt": prompt,
            }

        sanitized_prompt = g_result.sanitized_prompt

    # -------------------------------------------------------------
    # Step 2: Semantic & Prompt Cache
    # -------------------------------------------------------------
    cache_info: Dict[str, Any] = {"hit": False, "type": None, "similarity": 0.0}

    if req.use_cache:
        cached_resp, hit_type, score = app_cache.get(sanitized_prompt, model="ui_router")
        if cached_resp is not None:
            elapsed = time.time() - start_time
            cache_info = {"hit": True, "type": hit_type, "similarity": round(score, 3)}
            return {
                "success": True,
                "status": "cached",
                "response": cached_resp,
                "model_used": f"cache ({hit_type})",
                "stage": "cache_hit",
                "strategy": "DIRECT_LLM",
                "guardrail": guardrail_info,
                "cache": cache_info,
                "gateway": get_gateway_info("cheap"),
                "citations": [],
                "fused_queries": [],
                "latency_ms": round(elapsed * 1000, 2),
                "sanitized_prompt": sanitized_prompt,
            }
        else:
            cache_info["similarity"] = round(score, 3)

    # -------------------------------------------------------------
    # Step 3: Model Routing Decision (Cheap vs Smart)
    # -------------------------------------------------------------
    if req.strategy == "cascade":
        chosen_model = SMART
    elif req.strategy == "llm":
        chosen_model = classify_by_llm(sanitized_prompt)
    else:
        chosen_model = classify_by_rules(sanitized_prompt)

    # -------------------------------------------------------------
    # Step 4: Orchestrator (RAG Decision & Human-in-the-Loop Gateway)
    # -------------------------------------------------------------
    if req.use_orchestrator:
        strat, risk, reason, proposed_queries, target_docs = orchestrator.decide_strategy(
            sanitized_prompt, chosen_model=chosen_model
        )

        # 4a. Human-in-the-Loop required for high-risk / offensive security requests
        if strat == ExecutionStrategy.RAG_HUMAN_IN_THE_LOOP:
            action = orchestrator.create_pending_action(
                user_prompt=sanitized_prompt,
                model=chosen_model,
                strategy=strat,
                risk_level=risk,
                reason=reason,
                proposed_queries=proposed_queries,
                target_docs=target_docs,
            )
            elapsed = time.time() - start_time
            return {
                "success": True,
                "status": "hitl_pending",
                "action_id": action.action_id,
                "strategy": strat.value,
                "risk_level": risk.value,
                "reason": reason,
                "proposed_queries": action.proposed_queries,
                "target_docs": action.target_docs,
                "model_used": f"hitl_pending ({action.action_id})",
                "stage": "hitl_approval_required",
                "guardrail": guardrail_info,
                "cache": cache_info,
                "gateway": get_gateway_info(chosen_model),
                "latency_ms": round(elapsed * 1000, 2),
                "sanitized_prompt": sanitized_prompt,
            }

        # 4b. Automated RAG Pipeline (pgvector, Fusion, RRF, Deduplication)
        elif strat == ExecutionStrategy.RAG_AUTOMATED:
            rag_res = rag_engine.query(
                prompt=sanitized_prompt,
                model=chosen_model,
                fused_queries=proposed_queries if proposed_queries else None,
            )
            raw_answer = rag_res["answer"]
            ctx_texts = [c["content"] for c in rag_res.get("top_chunks", []) if isinstance(c, dict) and "content" in c]
            out_guard = output_guardrails.inspect(raw_answer, retrieved_context=ctx_texts)
            answer = out_guard.sanitized_output

            # Cache successful RAG response
            if req.use_cache:
                app_cache.set(sanitized_prompt, answer, model="ui_router")

            elapsed = time.time() - start_time
            return {
                "success": True,
                "status": "completed",
                "response": answer,
                "model_used": rag_res["model_used"],
                "strategy": strat.value,
                "stage": "rag_automated",
                "citations": rag_res["citations"],
                "fused_queries": rag_res["fused_queries"],
                "top_chunks": rag_res["top_chunks"],
                "dedup_count": rag_res["dedup_count"],
                "guardrail": guardrail_info,
                "output_guardrail": out_guard.to_dict(),
                "cache": cache_info,
                "gateway": get_gateway_info(chosen_model),
                "latency_ms": round(elapsed * 1000, 2),
                "sanitized_prompt": sanitized_prompt,
            }

        # 4c. Tool Calling Execution (GitHub REST API, MCP Adapters)
        elif strat == ExecutionStrategy.TOOL_CALL:
            tool_res = orchestrator.execute_with_tools(
                prompt=sanitized_prompt, chosen_model=chosen_model
            )
            raw_answer = tool_res["answer"]
            out_guard = output_guardrails.inspect(raw_answer)
            answer = out_guard.sanitized_output

            if req.use_cache:
                app_cache.set(sanitized_prompt, answer, model="ui_router")

            elapsed = time.time() - start_time
            return {
                "success": True,
                "status": "completed",
                "response": answer,
                "model_used": tool_res["model_used"],
                "strategy": strat.value,
                "stage": "tool_call_execution",
                "tool_calls": tool_res.get("tool_calls", []),
                "tool_results": tool_res.get("tool_results", []),
                "citations": [],
                "fused_queries": [],
                "guardrail": guardrail_info,
                "output_guardrail": out_guard.to_dict(),
                "cache": cache_info,
                "gateway": get_gateway_info(chosen_model),
                "latency_ms": round(elapsed * 1000, 2),
                "sanitized_prompt": sanitized_prompt,
            }


    # -------------------------------------------------------------
    # Step 5: Direct Upstream LLM Call (No RAG needed)
    # -------------------------------------------------------------
    try:
        completion = openai_client.chat.completions.create(
            model=chosen_model,
            messages=[{"role": "user", "content": sanitized_prompt}],
            max_tokens=600,
            temperature=0.2,
        )
        raw_answer = completion.choices[0].message.content or ""
        out_guard = output_guardrails.inspect(raw_answer)
        answer = out_guard.sanitized_output
        model_returned = completion.model or chosen_model
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "status": "error",
            "response": f"[GATEWAY ERROR]: {str(e)}",
            "model_used": chosen_model,
            "stage": "gateway_error",
            "strategy": "DIRECT_LLM",
            "guardrail": guardrail_info,
            "cache": cache_info,
            "gateway": get_gateway_info(chosen_model),
            "latency_ms": round(elapsed * 1000, 2),
            "sanitized_prompt": sanitized_prompt,
        }

    # Save to cache
    if req.use_cache:
        app_cache.set(sanitized_prompt, answer, model="ui_router")

    elapsed = time.time() - start_time
    return {
        "success": True,
        "status": "completed",
        "response": answer,
        "model_used": model_returned,
        "strategy": "DIRECT_LLM",
        "stage": f"direct_llm ({chosen_model})",
        "citations": [],
        "fused_queries": [],
        "guardrail": guardrail_info,
        "output_guardrail": out_guard.to_dict(),
        "cache": cache_info,
        "gateway": get_gateway_info(chosen_model),
        "latency_ms": round(elapsed * 1000, 2),
        "sanitized_prompt": sanitized_prompt,
    }


# -----------------------------------------------------------------------------
# Web UI Endpoint
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index_page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Gateway Studio — Orchestrator, pgvector RAG & HITL</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: rgba(17, 24, 39, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --primary: #6366f1;
      --primary-hover: #4f46e5;
      --accent: #06b6d4;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --radius: 12px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
      background: var(--bg);
      background-image: 
        radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(6, 182, 212, 0.12) 0px, transparent 50%);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    header {
      padding: 1.25rem 2rem;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(9, 13, 22, 0.6);
      backdrop-filter: blur(12px);
    }

    .brand { display: flex; align-items: center; gap: 0.75rem; }
    .brand-icon {
      width: 40px; height: 40px;
      background: linear-gradient(135deg, #6366f1, #06b6d4);
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; color: white; font-size: 1.15rem;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }
    .brand-title h1 { font-size: 1.15rem; font-weight: 700; letter-spacing: -0.02em; }
    .brand-title p { font-size: 0.8rem; color: var(--text-muted); }

    .header-badges { display: flex; gap: 0.75rem; align-items: center; }
    .status-badge {
      display: flex; align-items: center; gap: 0.5rem;
      font-size: 0.8rem; padding: 0.35rem 0.8rem; border-radius: 20px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34d399; font-weight: 500;
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: #34d399; box-shadow: 0 0 8px #34d399; }
    .db-badge {
      font-size: 0.8rem; padding: 0.35rem 0.8rem; border-radius: 20px;
      background: rgba(6, 182, 212, 0.12); border: 1px solid rgba(6, 182, 212, 0.3);
      color: #22d3ee; font-weight: 500;
    }

    main {
      max-width: 1280px; width: 100%;
      margin: 1.25rem auto; padding: 0 1.5rem;
      display: grid; grid-template-columns: 1fr 1fr;
      gap: 1.5rem; flex: 1;
    }

    .panel {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 1.25rem;
      display: flex; flex-direction: column; gap: 1rem;
      backdrop-filter: blur(16px);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.36);
    }

    .panel-header {
      display: flex; justify-content: space-between; align-items: center;
      padding-bottom: 0.75rem; border-bottom: 1px solid var(--card-border);
    }
    .panel-title { font-size: 0.95rem; font-weight: 600; color: #e2e8f0; }

    /* Controls Grid */
    .controls-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;
    }
    .control-item { display: flex; flex-direction: column; gap: 0.3rem; }
    .control-item label { font-size: 0.75rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    select, input[type="text"] {
      background: rgba(0, 0, 0, 0.35); border: 1px solid var(--card-border);
      border-radius: 8px; padding: 0.5rem 0.75rem; color: var(--text);
      font-size: 0.85rem; outline: none; font-family: inherit;
    }
    select:focus, input[type="text"]:focus, textarea:focus { border-color: var(--primary); }

    .toggle-row { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
    .toggle-group { display: flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; color: #cbd5e1; cursor: pointer; }
    .toggle-group input[type="checkbox"] { accent-color: var(--primary); cursor: pointer; }

    /* Prompt Box */
    .prompt-area { position: relative; display: flex; flex-direction: column; }
    textarea {
      width: 100%; height: 110px;
      background: rgba(0, 0, 0, 0.45); border: 1px solid var(--card-border);
      border-radius: 10px; padding: 0.75rem; color: var(--text);
      font-family: inherit; font-size: 0.88rem; line-height: 1.5; resize: none; outline: none;
    }

    /* Chips */
    .chips-title { font-size: 0.75rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.4rem; }
    .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
    .chip {
      background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 20px; padding: 0.3rem 0.65rem; font-size: 0.75rem; color: #cbd5e1;
      cursor: pointer; transition: all 0.2s ease;
    }
    .chip:hover { background: rgba(99, 102, 241, 0.15); border-color: var(--primary); color: #fff; transform: translateY(-1px); }
    .chip-hitl { border-color: rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.08); color: #fbbf24; }
    .chip-hitl:hover { background: rgba(245, 158, 11, 0.2); border-color: #f59e0b; color: #fde68a; }

    /* Buttons */
    .btn {
      background: linear-gradient(135deg, var(--primary), #4f46e5);
      border: none; border-radius: 10px; color: white;
      padding: 0.75rem 1rem; font-size: 0.9rem; font-weight: 600;
      cursor: pointer; display: flex; justify-content: center; align-items: center;
      gap: 0.5rem; transition: all 0.2s ease; box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
    }
    .btn:hover { background: linear-gradient(135deg, #4f46e5, #4338ca); transform: translateY(-1px); }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; }

    /* 6-Stage Pipeline Trace */
    .pipeline-trace {
      display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.5rem;
    }
    .stage-card {
      background: rgba(0, 0, 0, 0.3); border: 1px solid var(--card-border);
      border-radius: 8px; padding: 0.5rem; display: flex; flex-direction: column; gap: 0.2rem;
    }
    .stage-name { font-size: 0.68rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; }
    .stage-val { font-size: 0.78rem; font-weight: 600; font-family: 'JetBrains Mono', monospace; word-break: break-all; }

    .tag-allowed { color: #34d399; }
    .tag-sanitized { color: #38bdf8; }
    .tag-blocked { color: #f87171; }
    .tag-hit { color: #a78bfa; }
    .tag-miss { color: #94a3b8; }
    .tag-rag { color: #38bdf8; }
    .tag-tool { color: #f472b6; font-weight: 700; }
    .tag-hitl { color: #fbbf24; font-weight: 700; }
    .tag-direct { color: #22d3ee; font-weight: 700; }
    .tag-litellm { color: #c084fc; font-weight: 700; }
    .tag-openai { color: #34d399; font-weight: 700; }
    .chip-tool {
      border-color: rgba(244, 114, 182, 0.35);
      background: rgba(244, 114, 182, 0.08);
      color: #f472b6;
    }
    .chip-tool:hover {
      background: rgba(244, 114, 182, 0.18);
      border-color: #f472b6;
    }

    /* Gateway & Strategy Route Banner */
    .route-banner {
      background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.25);
      border-radius: 8px; padding: 0.5rem 0.8rem; font-size: 0.75rem;
      display: flex; justify-content: space-between; align-items: center;
      flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.6rem;
    }

    /* Human-in-the-Loop Approval Card */
    .hitl-container {
      background: rgba(245, 158, 11, 0.08);
      border: 1px solid rgba(245, 158, 11, 0.35);
      border-radius: 10px; padding: 1rem;
      display: flex; flex-direction: column; gap: 0.75rem;
      animation: pulseBorder 2s infinite;
    }
    @keyframes pulseBorder {
      0%, 100% { border-color: rgba(245, 158, 11, 0.35); }
      50% { border-color: rgba(245, 158, 11, 0.75); }
    }
    .hitl-header {
      display: flex; justify-content: space-between; align-items: center;
    }
    .hitl-title {
      display: flex; align-items: center; gap: 0.5rem;
      font-size: 0.88rem; font-weight: 700; color: #fbbf24;
    }
    .hitl-badge {
      background: #f59e0b; color: #000; font-size: 0.7rem; font-weight: 700;
      padding: 0.2rem 0.5rem; border-radius: 12px; text-transform: uppercase;
    }
    .hitl-reason {
      font-size: 0.82rem; color: #fde68a; background: rgba(0, 0, 0, 0.3);
      padding: 0.6rem; border-radius: 6px; border-left: 3px solid #f59e0b;
    }
    .hitl-queries-box {
      display: flex; flex-direction: column; gap: 0.35rem;
    }
    .hitl-queries-label {
      font-size: 0.72rem; font-weight: 600; color: #cbd5e1; text-transform: uppercase;
    }
    .hitl-textarea {
      width: 100%; height: 75px; background: rgba(0, 0, 0, 0.5);
      border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px;
      padding: 0.5rem; color: #e2e8f0; font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem; resize: none; outline: none;
    }
    .hitl-actions {
      display: flex; gap: 0.5rem; flex-wrap: wrap;
    }
    .btn-approve {
      background: #10b981; border: none; color: white;
      padding: 0.45rem 0.9rem; border-radius: 6px; font-weight: 600; font-size: 0.8rem;
      cursor: pointer; transition: background 0.2s;
    }
    .btn-approve:hover { background: #059669; }
    .btn-modify {
      background: #6366f1; border: none; color: white;
      padding: 0.45rem 0.9rem; border-radius: 6px; font-weight: 600; font-size: 0.8rem;
      cursor: pointer; transition: background 0.2s;
    }
    .btn-modify:hover { background: #4f46e5; }
    .btn-reject {
      background: #ef4444; border: none; color: white;
      padding: 0.45rem 0.9rem; border-radius: 6px; font-weight: 600; font-size: 0.8rem;
      cursor: pointer; transition: background 0.2s;
    }
    .btn-reject:hover { background: #dc2626; }

    /* Output & Citations Section */
    .output-box {
      flex: 1; background: rgba(0, 0, 0, 0.4); border: 1px solid var(--card-border);
      border-radius: 10px; padding: 1rem;
      font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #e2e8f0;
      line-height: 1.6; white-space: pre-wrap; overflow-y: auto; max-height: 380px;
    }
    .empty-state { color: #64748b; font-style: italic; text-align: center; margin-top: 4rem; }

    /* Citations Drawer */
    .citations-section {
      background: rgba(0, 0, 0, 0.25); border: 1px solid var(--card-border);
      border-radius: 8px; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.5rem;
    }
    .citations-header {
      font-size: 0.75rem; font-weight: 600; color: #38bdf8; text-transform: uppercase;
      display: flex; justify-content: space-between; align-items: center;
    }
    .citation-list { display: flex; flex-direction: column; gap: 0.4rem; }
    .citation-item {
      background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 6px; padding: 0.4rem 0.6rem; font-size: 0.75rem;
      display: flex; justify-content: space-between; align-items: center;
    }
    .citation-title { color: #cbd5e1; font-weight: 500; }
    .citation-meta { color: #94a3b8; font-size: 0.7rem; font-family: 'JetBrains Mono', monospace; }

    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      .pipeline-trace { grid-template-columns: repeat(2, 1fr); }
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="brand-icon">AG</div>
      <div class="brand-title">
        <h1>AI Gateway Studio</h1>
        <p>Guardrails • Caching • Router • Orchestrator • pgvector RAG • Human-in-the-Loop</p>
      </div>
    </div>
    <div class="header-badges">
      <div class="db-badge" style="background: rgba(244, 114, 182, 0.12); border-color: rgba(244, 114, 182, 0.3); color: #f472b6;">🛠️ GitHub API Tool</div>
      <div class="db-badge" style="background: rgba(56, 189, 248, 0.12); border-color: rgba(56, 189, 248, 0.3); color: #38bdf8;">📊 Prometheus & Grafana MCP</div>
      <div class="db-badge">PostgreSQL 16 + pgvector (5433)</div>
      <div class="status-badge">
        <span class="dot"></span>
        <span>Gateway (8080)</span>
      </div>
    </div>
  </header>

  <main>
    <!-- Left: Prompt & Controls -->
    <div class="panel">
      <div class="panel-header">
        <h2 class="panel-title">Request Configuration</h2>
        <button class="chip" onclick="reindexDocs()" style="background: rgba(6, 182, 212, 0.1); border-color: rgba(6, 182, 212, 0.3); color: #22d3ee;">Re-index Docs</button>
      </div>

      <!-- Controls -->
      <div class="controls-grid">
        <div class="control-item">
          <label>Router Model Tier</label>
          <select id="strategy">
            <option value="rules">Rules Classifier (Fast)</option>
            <option value="llm">LLM Classifier</option>
            <option value="cascade">Cascade Escalation</option>
          </select>
        </div>
        <div class="control-item">
          <label>PII Handling</label>
          <select id="piiAction">
            <option value="MASK">Mask / Redact PII (Safe)</option>
            <option value="BLOCK">Block on PII Detection</option>
          </select>
        </div>
      </div>

      <div class="toggle-row">
        <div class="toggle-group">
          <input type="checkbox" id="useOrchestrator" checked>
          <label for="useOrchestrator">Enable Orchestrator & RAG</label>
        </div>
        <div class="toggle-group">
          <input type="checkbox" id="useCache" checked>
          <label for="useCache">Enable Vector Cache</label>
        </div>
        <div class="toggle-group">
          <input type="checkbox" id="useGuardrails" checked>
          <label for="useGuardrails">Enable Guardrails</label>
        </div>
      </div>

      <!-- Textarea -->
      <div class="prompt-area">
        <textarea id="promptInput" placeholder="Ask about SeTakeOwnershipPrivilege, GitHub repos (octocat/Hello-World), Wordlists, or test HITL triggers..."></textarea>
      </div>

      <!-- Sample Chips -->
      <div>
        <div class="chips-title">Quick Test Prompts</div>
        <div class="chips">
          <div class="chip" onclick="setPrompt('What is the capital of Japan?')">Direct LLM (Capital)</div>
          <div class="chip" onclick="setPrompt('Can you tell me Japan\'s capital city?')">Semantic Cache (Hit)</div>
          <div class="chip" onclick="setPrompt('My email is sec@corp.com and API key is sk-123456789012345678901234. Summarize this safely.')">PII Masking</div>
          <div class="chip" onclick="setPrompt('Can you explain the purpose of SeTakeOwnershipPrivilege in Windows?')">RAG: Windows PrivEsc</div>
          <div class="chip" onclick="setPrompt('What are default wordlists available in Kali Linux according to the guide?')">RAG: Wordlists Guide</div>
          <div class="chip chip-hitl" onclick="setPrompt('Provide step-by-step commands to exploit SeTakeOwnershipPrivilege and take over system files.')">⚠️ HITL: SeTakeOwnership Exploit</div>
          <div class="chip chip-tool" onclick="setPrompt('Fetch GitHub repository details for octocat/Hello-World')">🛠️ GitHub: Repo Details</div>
          <div class="chip chip-tool" onclick="setPrompt('Search GitHub for litellm AI Gateway repositories and summarize results')">🛠️ GitHub: Search Repos</div>
          <div class="chip chip-tool" onclick="setPrompt('Read README file from octocat/Hello-World via GitHub tool')">🛠️ GitHub: File Content</div>
          <div class="chip chip-tool" onclick="setPrompt('Query Prometheus metrics for AI Gateway P99 latency and active alerts')">📊 Prometheus: P99 Latency & Alerts</div>
          <div class="chip chip-tool" onclick="setPrompt('Search Grafana dashboards for AI Gateway production telemetry and datasources')">📈 Grafana: Search Dashboards</div>
        </div>
      </div>

      <button id="sendBtn" class="btn" onclick="sendPrompt()">
        <span>Process through Gateway</span>
        <span>→</span>
      </button>

      <!-- Direct GitHub API Tool Runner -->
      <div style="background: rgba(244, 114, 182, 0.05); border: 1px solid rgba(244, 114, 182, 0.2); border-radius: 8px; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.5rem; margin-top: 0.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; font-weight: 700; color: #f472b6; text-transform: uppercase;">🛠️ Direct Tool Execution (GitHub REST API)</span>
          <span id="ghStatusBadge" style="font-size: 0.7rem; color: #94a3b8; font-family: 'JetBrains Mono', monospace;">Adapter: github_api</span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
          <select id="ghAction" onchange="onGhActionChange()" style="font-size: 0.78rem; padding: 0.35rem 0.6rem;">
            <option value="get_repo">Action: get_repo</option>
            <option value="search_repositories">Action: search_repositories</option>
            <option value="get_file_content">Action: get_file_content</option>
            <option value="list_issues">Action: list_issues</option>
            <option value="get_user">Action: get_user</option>
            <option value="list_commits">Action: list_commits</option>
          </select>
          <input type="text" id="ghParam1" value="octocat/Hello-World" placeholder="owner/repo (e.g. octocat/Hello-World)" style="font-size: 0.78rem; padding: 0.35rem 0.6rem;">
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <input type="text" id="ghParam2" placeholder="Path (e.g. README) or Query / Username" style="font-size: 0.78rem; padding: 0.35rem 0.6rem; flex: 1;">
          <button class="chip" onclick="executeGhDirect()" style="background: rgba(244, 114, 182, 0.2); border-color: rgba(244, 114, 182, 0.4); color: #f472b6; font-weight: 600; cursor: pointer;">Run Tool Directly</button>
        </div>
      </div>
    </div>


    <!-- Right: Pipeline Trace & Output -->
    <div class="panel">
      <div class="panel-header">
        <h2 class="panel-title">Gateway Execution Trace</h2>
        <button class="chip" onclick="clearCache()" style="background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3); color: #f87171;">Clear Cache</button>
      </div>

      <!-- 6-Stage Pipeline Status -->
      <div class="pipeline-trace">
        <div class="stage-card">
          <div class="stage-name">1. Guardrail</div>
          <div class="stage-val" id="traceGuardrail">—</div>
        </div>
        <div class="stage-card">
          <div class="stage-name">2. Cache</div>
          <div class="stage-val" id="traceCache">—</div>
        </div>
        <div class="stage-card">
          <div class="stage-name">3. Router</div>
          <div class="stage-val" id="traceRouter">—</div>
        </div>
        <div class="stage-card">
          <div class="stage-name">4. Orchestrator</div>
          <div class="stage-val" id="traceOrchestrator">—</div>
        </div>
        <div class="stage-card">
          <div class="stage-name">5. Gateway</div>
          <div class="stage-val" id="traceGateway">—</div>
        </div>
        <div class="stage-card">
          <div class="stage-name">6. Latency</div>
          <div class="stage-val" id="traceLatency">—</div>
        </div>
      </div>

      <!-- Human-in-the-Loop Container (Dynamically Rendered) -->
      <div id="hitlContainer" style="display: none;"></div>

      <!-- Grounded Citations (Dynamically Rendered for RAG) -->
      <div id="citationsSection" class="citations-section" style="display: none;">
        <div class="citations-header">
          <span>Grounded Sources (pgvector + RRF Ranking)</span>
          <span id="dedupCountBadge" style="font-size: 0.7rem; color: #94a3b8;"></span>
        </div>
        <div class="citation-list" id="citationList"></div>
      </div>

      <!-- Gateway Route & Strategy Banner -->
      <div id="routeBanner" class="route-banner" style="display: none;"></div>

      <!-- Output Display -->
      <div class="output-box" id="outputBox">
        <div class="empty-state">Submit a prompt to view sanitized request, routing decision, orchestrator strategy, and response.</div>
      </div>
    </div>
  </main>

  <script>
    let currentPendingActionId = null;

    function setPrompt(text) {
      document.getElementById('promptInput').value = text;
    }

    async function clearCache() {
      await fetch('/api/cache/clear', { method: 'POST' });
      alert('Semantic & Prompt Cache cleared!');
    }

    async function reindexDocs() {
      const btn = event.target;
      btn.innerText = 'Indexing...';
      try {
        const res = await fetch('/api/rag/ingest', { method: 'POST' });
        const data = await res.json();
        alert(`Indexed ${data.total_chunks} semantic chunks into ${data.database} in ${data.elapsed_seconds}s!`);
      } catch (e) {
        alert('Indexing failed: ' + e.message);
      } finally {
        btn.innerText = 'Re-index Docs';
      }
    }

    async function sendPrompt() {
      const prompt = document.getElementById('promptInput').value.trim();
      if (!prompt) return;

      const btn = document.getElementById('sendBtn');
      const outputBox = document.getElementById('outputBox');
      const hitlBox = document.getElementById('hitlContainer');
      const citationsSection = document.getElementById('citationsSection');
      const citationList = document.getElementById('citationList');

      hitlBox.style.display = 'none';
      citationsSection.style.display = 'none';
      citationList.innerHTML = '';

      btn.disabled = true;
      btn.innerText = 'Evaluating through Gateway & Orchestrator...';
      outputBox.innerHTML = '<span style="color: #94a3b8;">Executing: Guardrails -> Cache -> Router -> Orchestrator -> Gateway...</span>';

      const payload = {
        prompt: prompt,
        strategy: document.getElementById('strategy').value,
        use_cache: document.getElementById('useCache').checked,
        use_guardrails: document.getElementById('useGuardrails').checked,
        use_orchestrator: document.getElementById('useOrchestrator').checked,
        pii_action: document.getElementById('piiAction').value,
      };

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        renderPipelineTrace(data);

        // Check if Human-in-the-Loop was triggered
        if (data.status === 'hitl_pending') {
          currentPendingActionId = data.action_id;
          renderHitlCard(data);
          outputBox.innerHTML = '<span style="color: #fbbf24;">⏸️ Action paused. Awaiting human approval/query adjustment above.</span>';
        } else {
          // Regular completed answer or RAG response
          renderAnswer(data);
        }

      } catch (err) {
        outputBox.innerHTML = `<span style="color: #f87171;">Request Failed: ${err.message}</span>`;
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>Process through Gateway</span><span>→</span>';
      }
    }

    function renderPipelineTrace(data) {
      const traceGuardrail = document.getElementById('traceGuardrail');
      const traceCache = document.getElementById('traceCache');
      const traceRouter = document.getElementById('traceRouter');
      const traceOrchestrator = document.getElementById('traceOrchestrator');
      const traceGateway = document.getElementById('traceGateway');
      const traceLatency = document.getElementById('traceLatency');

      // 1. Guardrail
      if (data.guardrail) {
        if (!data.guardrail.passed) {
          traceGuardrail.innerHTML = '<span class="tag-blocked">BLOCKED</span>';
        } else if (data.guardrail.action === 'SANITIZED') {
          const piiKeys = Object.keys(data.guardrail.pii_entities || {}).join(', ');
          traceGuardrail.innerHTML = `<span class="tag-sanitized">MASKED (${piiKeys})</span>`;
        } else {
          traceGuardrail.innerHTML = '<span class="tag-allowed">PASSED</span>';
        }
      } else {
        traceGuardrail.innerHTML = '<span class="tag-miss">OFF</span>';
      }

      // 2. Cache
      if (data.cache && data.cache.hit) {
        traceCache.innerHTML = `<span class="tag-hit">${data.cache.type} (${data.cache.similarity})</span>`;
      } else if (data.cache && data.cache.similarity > 0) {
        traceCache.innerHTML = `<span class="tag-miss">MISS (${data.cache.similarity})</span>`;
      } else {
        traceCache.innerHTML = '<span class="tag-miss">MISS</span>';
      }

      // 3. Router
      traceRouter.innerText = data.model_used || 'cheap';

      // 4. Orchestrator Strategy
      if (data.status === 'hitl_pending') {
        traceOrchestrator.innerHTML = '<span class="tag-hitl">HITL_GATE</span>';
      } else if (data.stage === 'rag_automated') {
        traceOrchestrator.innerHTML = '<span class="tag-rag">RAG_AUTO</span>';
      } else if (data.strategy === 'TOOL_CALL' || data.stage === 'tool_call_execution') {
        traceOrchestrator.innerHTML = '<span class="tag-tool">TOOL_CALL</span>';
      } else if (data.strategy === 'DIRECT_LLM') {
        traceOrchestrator.innerHTML = '<span class="tag-direct">DIRECT_LLM</span>';
      } else {
        traceOrchestrator.innerHTML = `<span class="tag-allowed">${data.strategy || 'DIRECT'}</span>`;
      }

      // 5. Gateway Channel (LiteLLM vs OpenAI)
      if (data.gateway) {
        if (data.gateway.is_litellm) {
          traceGateway.innerHTML = `<span class="tag-litellm" title="Routed via ${data.gateway.gateway_service}">LiteLLM ➔ OpenAI</span>`;
        } else {
          traceGateway.innerHTML = `<span class="tag-openai" title="Direct Upstream">Direct OpenAI</span>`;
        }
      } else {
        traceGateway.innerHTML = '<span class="tag-litellm">LiteLLM</span>';
      }

      // 6. Latency
      traceLatency.innerText = (data.latency_ms || 0) + ' ms';
    }

    function renderHitlCard(data) {
      const hitlBox = document.getElementById('hitlContainer');
      const queriesStr = (data.proposed_queries || []).join('\\n');

      hitlBox.innerHTML = `
        <div class="hitl-container">
          <div class="hitl-header">
            <div class="hitl-title">
              <span>⚠️ Action Flagged by Orchestrator</span>
            </div>
            <span class="hitl-badge">${data.risk_level} RISK</span>
          </div>

          <div class="hitl-reason">
            <strong>Risk Rationale:</strong> ${data.reason}<br>
            <span style="font-size: 0.75rem; color: #fef08a;">Target Documents: ${(data.target_docs || []).join(', ') || 'Security Knowledge Base'}</span>
          </div>

          <div class="hitl-queries-box">
            <span class="hitl-queries-label">Proposed RAG-Fusion Search Queries (Editable by Human):</span>
            <textarea id="hitlQueriesInput" class="hitl-textarea">${queriesStr}</textarea>
          </div>

          <div class="hitl-actions">
            <button class="btn-approve" onclick="resolveHitl('approve')">✓ Approve & Execute RAG</button>
            <button class="btn-modify" onclick="resolveHitl('modify')">✏️ Execute with Modified Queries</button>
            <button class="btn-reject" onclick="resolveHitl('reject')">✕ Reject RAG (Direct Safe Guidance)</button>
          </div>
        </div>
      `;
      hitlBox.style.display = 'block';
    }

    async function resolveHitl(decision) {
      if (!currentPendingActionId) return;

      const outputBox = document.getElementById('outputBox');
      const queriesInput = document.getElementById('hitlQueriesInput');
      const queriesList = queriesInput ? queriesInput.value.split('\\n').map(q => q.trim()).filter(Boolean) : [];

      outputBox.innerHTML = `<span style="color: #38bdf8;">Executing decision: [${decision.toUpperCase()}]...</span>`;

      try {
        const res = await fetch('/api/hitl/respond', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action_id: currentPendingActionId,
            decision: decision,
            modified_query: queriesList[0] || '',
            modified_queries: queriesList,
          })
        });

        const data = await res.json();
        document.getElementById('hitlContainer').style.display = 'none';

        renderAnswer(data);
      } catch (e) {
        outputBox.innerHTML = `<span style="color: #f87171;">Action Resolution Failed: ${e.message}</span>`;
      }
    }

    function renderAnswer(data) {
      const outputBox = document.getElementById('outputBox');
      const routeBanner = document.getElementById('routeBanner');

      // Populate Route Banner (Strategy + Gateway info)
      if (data.gateway) {
        const isDirect = data.strategy === 'DIRECT_LLM' || (data.stage && data.stage.includes('direct_llm'));
        const isTool = data.strategy === 'TOOL_CALL' || (data.stage && data.stage.includes('tool_call'));
        const stratHtml = isTool
          ? '<span class="tag-tool" style="background: rgba(244, 114, 182, 0.12); border: 1px solid rgba(244, 114, 182, 0.3); padding: 0.2rem 0.5rem; border-radius: 4px;">🛠️ Orchestrator Strategy: TOOL_CALL (External GitHub REST API Invocation)</span>'
          : (isDirect
            ? '<span class="tag-direct">⚡ Orchestrator Strategy: DIRECT_LLM (General Knowledge — No RAG Search Needed)</span>'
            : '<span class="tag-rag">📚 Orchestrator Strategy: RAG_AUTOMATED (PostgreSQL pgvector Grounded Search)</span>');

        const gatewayHtml = data.gateway.is_litellm
          ? `<span class="tag-litellm">🌐 Gateway Channel: <strong>${data.gateway.gateway_service}</strong> ➔ Upstream Provider: <strong>${data.gateway.upstream_provider} (${data.gateway.upstream_model})</strong></span>`
          : `<span class="tag-openai">⚡ Upstream Channel: <strong>Direct OpenAI</strong> (${data.gateway.upstream_model})</span>`;

        routeBanner.innerHTML = `${stratHtml} ${gatewayHtml}`;
        routeBanner.style.display = 'flex';
      } else {
        routeBanner.style.display = 'none';
      }

      // Citations if RAG was run
      if (data.citations && data.citations.length > 0) {
        renderCitations(data.citations, data.dedup_count);
      } else {
        document.getElementById('citationsSection').style.display = 'none';
      }

      let formatted = '';
      if (data.sanitized_prompt && data.sanitized_prompt !== document.getElementById('promptInput').value.trim()) {
        formatted += `[Sanitized Prompt Sent to Gateway]:\\n${data.sanitized_prompt}\\n\\n`;
      }
      formatted += data.response;

      if (data.tool_results && data.tool_results.length > 0) {
        let toolsInfo = '\\n\\n═══════════════════════════════════════════════════════════\\n';
        toolsInfo += '🛠️ TOOL CALL DISPATCH TELEMETRY (Adapter Pattern)\\n';
        toolsInfo += '═══════════════════════════════════════════════════════════\\n';
        data.tool_results.forEach((tr, i) => {
          toolsInfo += `[Tool ${i+1}]: ${tr.tool} | Status: ${tr.result?.status || 'ok'}\\n`;
          toolsInfo += `[Arguments]: ${JSON.stringify(tr.arguments)}\\n`;
          if (tr.result && tr.result.rate_limit_remaining !== undefined) {
            toolsInfo += `[GitHub Rate Limit]: ${tr.result.rate_limit_remaining}/${tr.result.rate_limit_total} remaining\\n`;
          }
        });
        formatted += toolsInfo;
      }

      outputBox.innerText = formatted;
    }

    function renderCitations(citations, dedupCount) {
      const citationsSection = document.getElementById('citationsSection');
      const citationList = document.getElementById('citationList');
      const dedupBadge = document.getElementById('dedupCountBadge');

      citationList.innerHTML = '';
      dedupBadge.innerText = dedupCount > 0 ? `${dedupCount} duplicate chunk(s) filtered` : '';

      citations.forEach(c => {
        const item = document.createElement('div');
        item.className = 'citation-item';
        item.innerHTML = `
          <div class="citation-title">📄 ${c.title}</div>
          <div class="citation-meta">Pages ${c.pages} • RRF: ${c.rrf_score}</div>
        `;
        citationList.appendChild(item);
      });

      citationsSection.style.display = 'flex';
    }

    function onGhActionChange() {
      const act = document.getElementById('ghAction').value;
      const p1 = document.getElementById('ghParam1');
      const p2 = document.getElementById('ghParam2');

      if (act === 'get_repo' || act === 'list_issues' || act === 'list_commits') {
        p1.placeholder = 'owner/repo (e.g. octocat/Hello-World)';
        p2.placeholder = act === 'list_issues' ? 'State (open/closed/all)' : 'Optional ref / branch';
      } else if (act === 'get_file_content') {
        p1.placeholder = 'owner/repo (e.g. octocat/Hello-World)';
        p2.placeholder = 'File path (e.g. README or src/app.py)';
      } else if (act === 'search_repositories') {
        p1.placeholder = 'Search Query (e.g. ai gateway python)';
        p2.placeholder = 'Sort (stars, forks, updated)';
      } else if (act === 'get_user') {
        p1.placeholder = 'GitHub username (e.g. octocat)';
        p2.placeholder = 'Unused';
      }
    }

    async function executeGhDirect() {
      const act = document.getElementById('ghAction').value;
      const p1 = document.getElementById('ghParam1').value.trim();
      const p2 = document.getElementById('ghParam2').value.trim();
      const outputBox = document.getElementById('outputBox');
      const badge = document.getElementById('ghStatusBadge');

      outputBox.innerHTML = '<span style="color: #f472b6;">Executing GitHub REST API tool directly via /api/tools/execute...</span>';
      badge.innerText = 'Calling GitHub...';

      let params = { action: act };
      if (act === 'get_repo' || act === 'list_issues' || act === 'list_commits') {
        params.repo = p1;
        if (p2) params[act === 'list_issues' ? 'state' : 'ref'] = p2;
      } else if (act === 'get_file_content') {
        params.repo = p1;
        params.path = p2 || 'README';
      } else if (act === 'search_repositories') {
        params.query = p1 || 'ai gateway';
        if (p2) params.sort = p2;
      } else if (act === 'get_user') {
        params.username = p1 || 'octocat';
      }

      try {
        const res = await fetch('/api/tools/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tool_name: 'github_api',
            params: params,
          })
        });
        const data = await res.json();
        badge.innerText = data.success ? 'HTTP 200 OK' : 'Execution Failed';
        outputBox.innerText = `// Tool Execution Output via ToolRegistry: github_api\n// Elapsed: ${data.elapsed_ms}ms\n\n` + JSON.stringify(data.result, null, 2);
      } catch (e) {
        outputBox.innerHTML = `<span style="color: #f87171;">Tool execution failed: ${e.message}</span>`;
        badge.innerText = 'Error';
      }
    }

  </script>
</body>
</html>
"""
