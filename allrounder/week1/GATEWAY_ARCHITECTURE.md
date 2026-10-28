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

| Pattern | Architectural Layer | Package Directory | Implementation |
| :--- | :--- | :--- | :--- |
| **Ports & Adapters (Hexagonal)** | Vector Storage | [`storage/`](./storage/) | `VectorStore` port with `PgVectorStore` (PostgreSQL + HNSW) and `InMemoryVectorStore` (NumPy) adapters. |
| **Factory Method** | Storage Initialization | [`storage/`](./storage/) | `VectorStoreFactory.create()` probes DB connectivity and library presence, gracefully falling back with 0 crashes. |
| **Chain of Responsibility** | Inbound & Outbound Guardrails | [`guardrails/`](./guardrails/) | Sequential filters (`PayloadLengthFilter` $\to$ `PromptInjectionFilter` $\to$ `PIIMaskingFilter` $\to$ `ToxicityFilter`). |
| **Filter / Interceptor** | Outbound Guardrails | [`guardrails/`](./guardrails/) | Validates LLM responses for secret leaks, PII, hallucination, and JSON formatting before client delivery. |
| **Adapter Pattern** | Tool & MCP Execution | [`tools/`](./tools/) | Uniform `BaseTool` interface wrapping RAG search (`RagKnowledgeTool`), external REST APIs (`RestApiToolAdapter`), and MCP servers (`MCPToolAdapter`). |
| **Plugin / Registry** | Tool Central Registry | [`tools/`](./tools/) | `ToolRegistry` managing dynamic tool discovery, LLM function calling schema generation, and execution dispatching. |
| **Strategy Pattern** | Smart Router | [`routing/`](./routing/) | `RoutingStrategy` with interchangeable strategies: `RuleBasedStrategy`, `LLMJudgeStrategy`, and `CostCascadingStrategy`. |
| **Finite State Machine (FSM)**| Orchestration & HITL | [`orchestration/`](./orchestration/) | Stateful tracking: `RECEIVED` $\to$ `GUARD_INPUT` $\to$ `CACHE_CHECK` $\to$ `INTENT_ROUTED` $\to$ `PAUSED_HITL` $\to$ `COMPLETED`. |
| **Command Pattern** | Human-in-the-Loop Gateway | [`orchestration/`](./orchestration/) | `PendingAction` command object encapsulating paused queries, proposed actions, and reviewer decision hooks. |
| **Cache-Aside Pattern** | Dual-Tier Cache | [`caching/`](./caching/) | Exact SHA-256 hash lookup $O(1)$ 0ms latency + Semantic vector similarity checking against Redis/embeddings. |
| **Pipeline Pattern** | RAG Ingestion & Retrieval | [`rag/`](./rag/) | Decoupled semantic chunking (`chunker.py`), RAG-Fusion & RRF ranking (`fusion.py`), and grounded synthesis (`engine.py`). |

---

## Detailed Layer Specifications

### Layer 1: Edge Reverse Proxy (Nginx / Caddy)
- **Port:** `8080` (API) / `8000` (Web Dashboard)
- **Configuration:** [`nginx.conf`](./nginx.conf), [`nginx.docker.conf`](./nginx.docker.conf), [`Caddyfile`](./Caddyfile)
- Disables Server-Sent Events (SSE) buffering via `proxy_buffering off;` to allow smooth token streaming.
- Enforces connection rate limits (`limit_req_zone`) to stop DDoS attempts at the OS TCP level before touching Python.

### Layer 2: Inbound Guardrails & Defensive Shields
- **Package:** [`guardrails/`](./guardrails/) (`input_guardrails.py`, `base.py`)
- **Pattern:** Chain of Responsibility
- **Prompt Injection:** Heuristically halts attacks like `ignore previous instructions`, `DAN`, `developer mode`, and `<system>` override tags in `< 1ms`.
- **Inbound PII Masking:** Replaces sensitive user emails, credit cards, SSNs, and API keys with typed tokens (e.g., `[REDACTED_EMAIL]`, `[REDACTED_API_KEY]`).

### Layer 3: Dual-Layer Caching Engine
- **Package:** [`caching/`](./caching/) (`semantic_cache.py`, `base.py`)
- **Pattern:** Cache-Aside & Strategy
- **Exact Hash Match:** $O(1)$ lookup via `sha256(model:normalized_prompt)`. Latency: `< 0.001s`, cost: `$0.00`.
- **Semantic Vector Cache:** Generates dense embeddings (`text-embedding-3-small`) and evaluates cosine similarity. If similarity $\ge 0.85$, returns cached response with 90%+ latency reduction.

### Layer 4: Smart Router & Model Virtualization
- **Package:** [`routing/`](./routing/) (`router.py`, `strategies.py`, `base.py`)
- **Pattern:** Strategy Pattern
- Dynamically assigns queries to:
  - **`cheap` (`gpt-4o-mini`)**: For simple questions, summaries, keyword searches, and intent classification.
  - **`smart` (`gpt-4o` / `claude-3-7`)**: For complex reasoning, multi-step code generation, and critical evaluations.

### Layer 5: Orchestrator & Human-in-the-Loop (HITL) Gateway
- **Package:** [`orchestration/`](./orchestration/) (`orchestrator.py`, `state.py`)
- **Pattern:** Finite State Machine (FSM) & Command Pattern
- Decides execution path:
  1. `DIRECT_LLM`: Non-security general knowledge questions bypass document retrieval.
  2. `RAG_AUTOMATED`: Benign internal documentation queries run automated RAG-Fusion, PGVector search, and RRF ranking.
  3. `RAG_HUMAN_IN_THE_LOOP`: High-risk or offensive security requests (exploits, password cracking, privilege takeover) are **paused**. Generates a `PendingAction` and requires human operator sign-off (`approve`, `modify`, or `reject`).

### Layer 6: Pluggable Tools, External APIs & MCP (Model Context Protocol)
- **Package:** [`tools/`](./tools/) (`registry.py`, `base.py`, `rag_tool.py`, `rest_tool.py`, `mcp_tool.py`)
- **Pattern:** Adapter Pattern & Plugin Registry
- **`RagKnowledgeTool`**: Exposes internal document search as an LLM tool.
- **`RestApiToolAdapter`**: Calls external REST APIs (Jira, GitHub, Slack, webhooks) without modifying orchestrator code.
- **`MCPToolAdapter`**: Bridges standard Model Context Protocol (MCP) servers (PostgreSQL MCP, Git MCP, Filesystem MCP) into function calling schemas.

### Layer 7: Resilient Vector Storage (PostgreSQL + pgvector + In-Memory)
- **Package:** [`storage/`](./storage/) (`base.py`, `pgvector_store.py`, `in_memory_store.py`, `factory.py`)
- **Pattern:** Ports & Adapters (Hexagonal) & Factory Method
- **`PgVectorStore`**: PostgreSQL 16 + pgvector with HNSW vector index (`USING hnsw (embedding vector_cosine_ops)`). Uses connection pooling.
- **Resilient Type Adaptation:** Works with native JSON vector strings or the `pgvector` Python library.
- **`InMemoryVectorStore`**: High-performance NumPy cosine similarity fallback if the database is offline.

### Layer 8: Output Guardrails & Groundedness Shield
- **Package:** [`guardrails/`](./guardrails/) (`output_guardrails.py`, `base.py`)
- **Pattern:** Filter / Interceptor & Chain of Responsibility
- **Secret Leakage Blocker:** Redacts leaked credentials (`sk-...`, GitHub tokens, AWS keys, database connection URIs) from LLM responses before returning them to users.
- **Groundedness Verifier:** Calculates token overlap against retrieved context chunks to detect and flag hallucinations.
- **JSON Schema Enforcer:** Guarantees valid structured output when required.

---

## Directory Organization (`allrounder/week1/`)

```text
allrounder/week1/
├── app.py                          # FastAPI backend & interactive web dashboard
├── docker-compose.gateway.yml      # Docker stack (Nginx, LiteLLM, Redis, PostgreSQL)
├── GATEWAY_ARCHITECTURE.md         # Complete system architecture specification
├── litellm_config.yaml             # LiteLLM proxy configuration
├── nginx.conf                      # Nginx edge reverse proxy config (local)
├── nginx.docker.conf               # Nginx edge reverse proxy config (Docker)
├── Caddyfile                       # Optional Caddy reverse proxy config
├── __init__.py                     # Package entry point exposing all modular layers
│
├── guardrails/                     # Chain of Responsibility & Filter / Interceptor Pattern
│   ├── __init__.py
│   ├── base.py                     # BaseGuardrailFilter, GuardrailPipeline, GuardrailContext
│   ├── input_guardrails.py         # Injection, PII Masking, Length, Toxicity filters
│   └── output_guardrails.py        # Secret Leakage, Groundedness, Schema filters
│
├── caching/                        # Cache-Aside Pattern & Dual-Tier Strategy
│   ├── __init__.py
│   ├── base.py                     # BaseCache abstract interface & CacheEntry dataclass
│   └── semantic_cache.py           # Exact O(1) hash + Semantic Vector Cosine similarity cache
│
├── routing/                        # Strategy Pattern for Model Routing
│   ├── __init__.py
│   ├── base.py                     # RoutingStrategy interface & RoutingDecision model
│   ├── strategies.py               # RuleBasedStrategy, LLMJudgeStrategy, CostCascadingStrategy
│   └── router.py                   # SmartRouter context class
│
├── orchestration/                  # Finite State Machine (FSM) & Command Pattern (HITL)
│   ├── __init__.py
│   ├── state.py                    # ExecutionState, ExecutionStrategy, RiskLevel, PendingAction
│   └── orchestrator.py             # Stateful Orchestrator coordinating execution & HITL
│
├── tools/                          # Adapter Pattern & Plugin Registry Pattern
│   ├── __init__.py
│   ├── base.py                     # BaseTool abstract interface & ToolDefinition schema
│   ├── rag_tool.py                 # RagKnowledgeTool adapter
│   ├── rest_tool.py                # RestApiToolAdapter (Jira, GitHub, Slack)
│   ├── mcp_tool.py                 # MCPToolAdapter (Model Context Protocol)
│   └── registry.py                 # ToolRegistry discovery and dispatch manager
│
├── storage/                        # Ports & Adapters (Hexagonal) & Factory Method
│   ├── __init__.py
│   ├── base.py                     # VectorStore port & Chunk entity
│   ├── pgvector_store.py           # PostgreSQL 16 + pgvector adapter (pool + HNSW)
│   ├── in_memory_store.py          # Resilient NumPy in-memory fallback adapter
│   └── factory.py                  # VectorStoreFactory with capability detection
│
├── rag/                            # Pipeline Pattern for Knowledge Retrieval
│   ├── __init__.py
│   ├── chunker.py                  # Boundary-aware semantic chunking
│   ├── fusion.py                   # RAG-Fusion query expansion & Reciprocal Rank Fusion (RRF)
│   └── engine.py                   # RagEngine pipeline coordinator
│
├── tests/                          # Unified Automated Verification Suites
│   ├── __init__.py
│   ├── test_enterprise_architecture.py # Unit tests for all design patterns & layers
│   ├── test_caching.py             # Exact & semantic cache benchmarks
│   └── test_reverse_proxy.py       # Reverse proxy, health, and rate-limiting tests
│
└── docs/                           # Indexed Knowledge Base
    ├── 1792861009005.pdf           # Windows Privilege Escalation: SeTakeOwnershipPrivilege
    ├── 1792907264681.pdf           # AWS: Penetration Testing Lab Setup
    ├── 1792907573179.pdf           # PostgreSQL Penetration Testing
    └── 1793025397798.pdf           # Comprehensive Guide on Wordlists
```

---

## Docker Infrastructure Stack (`docker-compose.gateway.yml`)

The production AI Gateway relies on four containerized infrastructure services orchestrated via Docker Compose:

| Container Service | Image | Host Port | Purpose |
| :--- | :--- | :--- | :--- |
| **`nginx`** | `nginx:alpine` | `8080:80` | Edge reverse proxy, IP rate limiting, DDoS protection, SSE streaming pass-through (`proxy_buffering off;`). |
| **`litellm`** | `ghcr.io/berriai/litellm:main-latest` | `4000:4000` | AI Gateway, virtual model routing (`cheap` vs `smart`), spend tracking, multi-provider failover. |
| **`redis`** | `redis/redis-stack-server:latest` | `6379:6379` | Exact prompt hash caching $O(1)$ and semantic vector similarity search cache. |
| **`pgvector`** | `pgvector/pgvector:pg16` | `5433:5432` | PostgreSQL 16 database with `pgvector` extension and HNSW vector indexing for RAG knowledge chunks. |

### Complete `docker-compose.gateway.yml` Script

```yaml
services:
  # -----------------------------------------------------------------------------
  # 1. Edge Reverse Proxy (Nginx)
  # - TLS termination, IP-based rate limiting, DDoS buffer, and SSE stream pass-through
  # -----------------------------------------------------------------------------
  nginx:
    image: nginx:alpine
    container_name: ai_gateway_nginx
    restart: unless-stopped
    ports:
      - "8080:80"      # Public entry point (80/443 in production)
    volumes:
      - ./nginx.docker.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - litellm
    networks:
      - ai_gateway_net

  # -----------------------------------------------------------------------------
  # 2. AI Gateway Layer (LiteLLM)
  # - Model routing ("cheap" vs "smart"), virtual keys, budgets, retry/fallbacks
  # - Exact Match & Semantic Vector Caching enabled via config.yaml
  # -----------------------------------------------------------------------------
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: ai_gateway_litellm
    restart: unless-stopped
    volumes:
      - ./litellm_config.yaml:/app/config.yaml:ro
    ports:
      - "4000:4000"
    command: ["--config", "/app/config.yaml", "--port", "4000"]
    env_file:
      - ../.env
    environment:
      - STORE_MODEL_IN_DB=True
      - REDIS_URL=redis://redis:6379
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - ai_gateway_net

  # -----------------------------------------------------------------------------
  # 3. Cache & Vector Store (Redis Stack with Vector Search)
  # - Powers exact prompt caching and semantic vector similarity search
  # -----------------------------------------------------------------------------
  redis:
    image: redis/redis-stack-server:latest
    container_name: ai_gateway_redis
    restart: unless-stopped
    environment:
      - REDIS_ARGS=--save 60 1 --loglevel notice
    ports:
      - "6379:6379"    # Expose for local testing/monitoring
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - ai_gateway_net

  # -----------------------------------------------------------------------------
  # 4. Vector Database (PostgreSQL 16 with pgvector extension)
  # - Used for document storage, semantic chunk embeddings, and similarity search
  # -----------------------------------------------------------------------------
  pgvector:
    image: pgvector/pgvector:pg16
    container_name: ai_gateway_pgvector
    restart: unless-stopped
    environment:
      - POSTGRES_DB=rag_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    ports:
      - "5433:5432"    # Map to host port 5433 to avoid collision with local Postgres on 5432
    volumes:
      - pgvector_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d rag_db"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - ai_gateway_net

volumes:
  pgvector_data:

networks:
  ai_gateway_net:
    driver: bridge
```

---

## Verification & Execution Guide

### 0. Start Containerized Infrastructure Stack
```bash
docker compose -f allrounder/week1/docker-compose.gateway.yml up -d
```
Check running container statuses and health probes:
```bash
docker compose -f allrounder/week1/docker-compose.gateway.yml ps
```

### 1. Run Complete Architecture Test Suite
```bash
python3 allrounder/week1/tests/test_enterprise_architecture.py
```
*Verifies Storage Abstraction, Guardrails Chain of Responsibility, Cache-Aside, Strategy Routing, Tool/MCP Registry, and Orchestrator FSM.*

### 2. Run RAG Pipeline with PostgreSQL + pgvector
```bash
python3 allrounder/week1/RagEngine.py
```

### 3. Run Cache Benchmarks
```bash
python3 allrounder/week1/tests/test_caching.py
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

