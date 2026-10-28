# Enterprise Multi-Layer Production AI Gateway & Agentic Architecture

```
User / Web UI / Clients
        │
        ▼ (Port 8000 Web UI / Port 80/8080 API)
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 1: Edge Reverse Proxy & API Gateway (Nginx / Caddy / Envoy)     │
│  - TLS Termination (HTTPS / SSL certificates)                          │
│  - IP-based DDoS Protection, Rate Limiting & Connection Throttling     │
│  - Large Payload Limits (50MB+ for vision / audio uploads)             │
│  - SSE Streaming Optimization (proxy_buffering off)                    │
│  - Health Probes (/healthz)                                            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 2: Input Guardrails & Defenses (Chain of Responsibility)        │
│  - Prompt Injection & Jailbreak Neutralization (< 1ms)                 │
│  - Inbound PII Shield: Masking / Redaction (Emails, API Keys, Cards)   │
│  - Toxic / Malicious Intent Rejection                                  │
│  - Character & Payload Length Protections                              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Sanitized Request
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 3: Exact & Semantic Caching (Cache-Aside Pattern)               │
│  - Exact Prompt Hash: O(1) 0ms latency ($0.00 cost)                    │
│  - Semantic Vector Similarity: Cosine >= 0.85 (Redis Stack / Memory)   │
└───────────────────┬───────────────────────────────┬────────────────────┘
                    │ Cache Hit (Instant)           │ Cache Miss
                    ▼                               ▼
            [Return Response]       ┌────────────────────────────────────┐
                                    │ Layer 4: Smart Router & Classifier │
                                    │ - Deterministic Rules + Heuristics │
                                    │ - Model Selection: cheap vs smart  │
                                    │ - Execution Strategy Selector      │
                                    └─────────────────┬──────────────────┘
                                                      │
                                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 5: Intelligent Orchestrator & State Machine (FSM / HITL)        │
│  - DIRECT_LLM: General queries bypassed directly to upstream           │
│  - RAG_AUTOMATED: Safe internal technical document search              │
│  - RAG_HUMAN_IN_THE_LOOP (HITL): High-risk offensive actions gated     │
│  - TOOL_CALL: External REST API & MCP dispatch                         │
└───────────────┬─────────────────────────────┬──────────────────────────┘
                │                             │
                ▼ (Automated RAG / Tools)     ▼ (Pending HITL Action)
┌────────────────────────────────┐   ┌───────────────────────────────────┐
│ Layer 6: Tools & MCP Adapters  │   │ Human Security Reviewer Approval  │
│ (Adapter / Plugin Pattern)     │   │ - Approve: executes query         │
│ - RagKnowledgeTool (PgVector)  │   │ - Modify: human rewrites search   │
│ - RestApiToolAdapter (Jira/APIs│   │ - Reject: defensive educational   │
│ - MCPToolAdapter (Model Context│   └─────────────────┬─────────────────┘
│   Protocol: Filesystem, Git)   │                     │
└───────────────┬────────────────┘                     │
                │                                      │
                ▼                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 7: AI Gateway & Provider Virtualization (LiteLLM)               │
│  - Virtual Model Aliases ("cheap", "smart", "vision")                  │
│  - Multi-Provider Failover: OpenAI -> Anthropic -> Local (Ollama)      │
│  - Spend, Token Budgeting & Latency Observability                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Generated Raw Answer
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 8: Output Guardrails & Groundedness Shield (Filter Pattern)     │
│  - Secret / Credential Leakage Prevention (sk-..., ghp_..., DB URLs)   │
│  - Groundedness / Hallucination Verification against retrieved chunks  │
│  - Outbound PII Redaction                                              │
│  - Strict JSON Schema & Type Guard                                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Validated, Safe Answer
                                    ▼
                              User / Client
```

---

## Software Engineering Design Patterns Applied

| Pattern | Architectural Layer | Implementation |
| :--- | :--- | :--- |
| **Ports & Adapters (Hexagonal)** | Vector Storage (`storage/`) | `VectorStore` port with `PgVectorStore` (PostgreSQL + HNSW) and `InMemoryVectorStore` (NumPy) adapters. |
| **Factory Method** | Storage Initialization | `VectorStoreFactory.create()` probes DB connectivity and library presence, gracefully falling back with 0 crashes. |
| **Chain of Responsibility** | Inbound Guardrails (`InputGuardrails.py`) | Sequential filter checks (Payload $\to$ Injection $\to$ PII $\to$ Toxicity). |
| **Filter / Interceptor** | Outbound Guardrails (`OutputGuardrails.py`) | Validates LLM responses for secret leaks, PII, hallucination, and JSON formatting before client delivery. |
| **Plugin / Adapter** | Tool & MCP Registry (`ToolRegistry.py`) | Standard `BaseTool` interface wrapping RAG search, external REST endpoints, and Model Context Protocol (MCP) servers. |
| **Strategy Pattern** | Smart Router (`SmartRouter.py`) | Rules-based heuristics, LLM classification, and cost-cascading fallbacks. |
| **Finite State Machine (FSM)**| Orchestration (`Orchestrator.py`) | Stateful tracking: `PENDING_ACTION` $\to$ `HUMAN_REVIEW` $\to$ `APPROVED/REJECTED` $\to$ `EXECUTION`. |
| **Cache-Aside** | Dual-Layer Cache (`SemanticCache.py`) | Exact SHA-256 hash lookup + Semantic vector similarity checking against Redis. |

---

## Detailed Layer Specifications

### Layer 1: Edge Reverse Proxy (Nginx / Caddy)
- **Port:** `8080` (API) / `8000` (Web Dashboard)
- **Configuration:** [`nginx.conf`](./nginx.conf), [`nginx.docker.conf`](./nginx.docker.conf)
- Disables Server-Sent Events (SSE) buffering via `proxy_buffering off;` to allow smooth token streaming.
- Enforces connection rate limits (`limit_req_zone`) to stop DDoS attempts at the OS TCP level before touching Python.

### Layer 2: Input Guardrails & Defensive Shields
- **File:** [`InputGuardrails.py`](./InputGuardrails.py)
- **Prompt Injection:** Heuristically halts attacks like `ignore previous instructions`, `DAN`, `developer mode`, and `<system>` override tags in `< 1ms`.
- **Inbound PII Masking:** Replaces sensitive user emails, credit cards, SSNs, and API keys with typed tokens (e.g., `[REDACTED_EMAIL]`, `[REDACTED_API_KEY]`).

### Layer 3: Dual-Layer Caching Engine
- **File:** [`SemanticCache.py`](./SemanticCache.py)
- **Exact Hash Match:** $O(1)$ lookup via `sha256(model:normalized_prompt)`. Latency: `< 0.001s`, cost: `$0.00`.
- **Semantic Vector Cache:** Generates dense embeddings (`text-embedding-3-small`) and evaluates cosine similarity. If similarity $\ge 0.85$, returns cached response with 90%+ latency reduction.

### Layer 4: Smart Router & Model Virtualization
- **File:** [`SmartRouter.py`](./SmartRouter.py)
- Dynamically assigns queries to:
  - **`cheap` (`gpt-4o-mini`)**: For simple questions, summaries, keyword searches, and intent classification.
  - **`smart` (`gpt-4o` / `claude-3-7`)**: For complex reasoning, multi-step code generation, and critical evaluations.

### Layer 5: Orchestrator & Human-in-the-Loop (HITL) Gateway
- **File:** [`Orchestrator.py`](./Orchestrator.py)
- Decides execution path:
  1. `DIRECT_LLM`: Non-security general knowledge questions bypass document retrieval.
  2. `RAG_AUTOMATED`: Benign internal documentation queries run automated RAG-Fusion, PGVector search, and RRF ranking.
  3. `RAG_HUMAN_IN_THE_LOOP`: High-risk or offensive security requests (exploits, password cracking, privilege takeover) are **paused**. Generates a `PendingAction` and requires human operator sign-off (`approve`, `modify`, or `reject`).

### Layer 6: Pluggable Tools, External APIs & MCP (Model Context Protocol)
- **File:** [`ToolRegistry.py`](./ToolRegistry.py)
- **`RagKnowledgeTool`**: Exposes internal document search as an LLM tool.
- **`RestApiToolAdapter`**: Calls external REST APIs (Jira, GitHub, Slack, webhooks) without modifying orchestrator code.
- **`MCPToolAdapter`**: Bridges standard Model Context Protocol (MCP) servers (PostgreSQL MCP, Git MCP, Filesystem MCP) into function calling schemas.

### Layer 7: Resilient Vector Storage (PostgreSQL + pgvector + In-Memory)
- **Package:** [`storage/`](./storage/)
- **`PgVectorStore`**: PostgreSQL 16 + pgvector with HNSW vector index (`USING hnsw (embedding vector_cosine_ops)`). Uses connection pooling.
- **Resilient Type Adaptation:** Works with native JSON vector strings or the `pgvector` Python library.
- **`InMemoryVectorStore`**: High-performance NumPy cosine similarity fallback if the database is offline.

### Layer 8: Output Guardrails & Groundedness Shield
- **File:** [`OutputGuardrails.py`](./OutputGuardrails.py)
- **Secret Leakage Blocker:** Redacts leaked credentials (`sk-...`, GitHub tokens, AWS keys, database connection URIs) from LLM responses before returning them to users.
- **Groundedness Verifier:** Calculates token overlap against retrieved context chunks to detect and flag hallucinations.
- **JSON Schema Enforcer:** Guarantees valid structured output when required.

---

## Directory Organization (`allrounder/week1/`)

```text
allrounder/week1/
├── storage/
│   ├── __init__.py               # Storage package exports
│   ├── base.py                   # Chunk dataclass & VectorStore abstract interface
│   ├── pgvector_store.py         # PostgreSQL + pgvector adapter with connection pool & HNSW
│   ├── in_memory_store.py        # Resilient NumPy vector store fallback
│   └── factory.py                # VectorStoreFactory with capability detection
├── InputGuardrails.py            # Layer 2: Inbound prompt injection & PII shield
├── SemanticCache.py              # Layer 3: Dual-layer exact & semantic vector cache
├── SmartRouter.py                # Layer 4: Model routing & cost-cascading
├── Orchestrator.py               # Layer 5: FSM orchestrator with Human-in-the-Loop gateway
├── ToolRegistry.py               # Layer 6: Extensible MCP & REST API tool registry
├── RagEngine.py                  # Knowledge retrieval: Fusion, RRF ranking, & pgvector
├── OutputGuardrails.py           # Layer 8: Outbound secret leakage & groundedness checks
├── app.py                        # FastAPI backend & interactive web dashboard
├── litellm_config.yaml           # LiteLLM proxy configuration
├── docker-compose.gateway.yml    # Docker stack (Nginx, LiteLLM, Redis, PostgreSQL)
├── test_enterprise_architecture.py # Unit tests for all architectural layers
├── test_caching.py               # Cache benchmarks & verification
└── test_reverse_proxy.py         # Reverse proxy & rate-limit verification
```

---

## Verification & Execution Guide

### 1. Run Complete Architecture Test Suite
```bash
python3 allrounder/week1/test_enterprise_architecture.py
```
*Verifies Storage Abstraction, Input Guardrails, Output Guardrails, Tool & MCP Registry, and Orchestrator.*

### 2. Run RAG with PostgreSQL + pgvector
```bash
python3 allrounder/week1/RagEngine.py
```

### 3. Run Cache Benchmarks
```bash
python3 allrounder/week1/test_caching.py
```

### 4. Launch Interactive Web Dashboard
```bash
python3 -m uvicorn allrounder.week1.app:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser.

### 5. Inspect Registered Tools & MCP Endpoints
```bash
curl -s http://localhost:8000/api/tools | jq .
```

### 6. Verify PostgreSQL Database Chunks
```bash
docker exec -it ai_gateway_pgvector psql -U postgres -d rag_db -c "SELECT id, title, page_start, substring(content from 1 for 80) FROM rag_chunks LIMIT 3;"
```
