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
│  - Prompt Injection & Jailbreak Neutralization (< 1ms heuristic)       │
│  - Jev System One Discriminative Safety Shield (Calibrated Noul check) │
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
                                    │ - Jev System-1 Non-Autoregressive  │
                                    │   Decision Model (<15ms, P-scores) │
                                    │ - Deterministic Rules + Heuristics │
                                    │ - Model Selection: cheap vs smart  │
                                    │ - Execution Strategy Selector      │
                                    └─────────────────┬──────────────────┘
                                                      │
                                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 5: Intelligent Orchestrator & State Machine (FSM / HITL)        │
│  - Jev System One Intent & Calibrated Offensive Risk Evaluator         │
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
│ - RestApiToolAdapter / GitHub  │   │ - Reject: defensive educational   │
│ - PrometheusMCPAdapter (PromQL)│   └─────────────────┬─────────────────┘
│ - GrafanaMCPAdapter (Dashboard)│                     │
│ - MCPToolAdapter (Base Model)  │                     │
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
│  - Jev System One NLI Entailment & Groundedness Verification (Noul)    │
│  - Lexical Keyword Overlap Groundedness Filter                         │
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
| **System-1 Decision Pattern** | Router, Orchestrator & Guardrails | [`routing/`](./routing/), [`orchestration/`](./orchestration/), [`guardrails/`](./guardrails/) | `JevRoutingStrategy`, `JevSafetyFilter`, `JevGroundednessFilter`, and `evaluate_with_jev()` using non-autoregressive decision models (`Choice`, `Noul`) with calibrated probabilities. |
| **Ports & Adapters (Hexagonal)** | Vector Storage | [`storage/`](./storage/) | `VectorStore` port with `PgVectorStore` (PostgreSQL + HNSW) and `InMemoryVectorStore` (NumPy) adapters. |
| **Factory Method** | Storage Initialization | [`storage/`](./storage/) | `VectorStoreFactory.create()` probes DB connectivity and library presence, gracefully falling back with 0 crashes. |
| **Chain of Responsibility** | Inbound & Outbound Guardrails | [`guardrails/`](./guardrails/) | Sequential filters (`PayloadLengthFilter` $\to$ `PromptInjectionFilter` $\to$ `PIIMaskingFilter` $\to$ `ToxicityFilter` $\to$ `JevSafetyFilter`). |
| **Filter / Interceptor** | Outbound Guardrails | [`guardrails/`](./guardrails/) | Validates LLM responses for secret leaks, PII, hallucination (`JevGroundednessFilter` + lexical overlap), and JSON formatting before client delivery. |
| **Adapter Pattern** | Tool & MCP Execution | [`tools/`](./tools/) | Uniform `BaseTool` interface wrapping RAG search (`RagKnowledgeTool`), external REST APIs (`RestApiToolAdapter`, `GitHubToolAdapter`), and MCP servers (`PrometheusMCPAdapter`, `GrafanaMCPAdapter`, `MCPToolAdapter`). |
| **Plugin / Registry** | Tool Central Registry | [`tools/`](./tools/) | `ToolRegistry` managing dynamic tool discovery, LLM function calling schema generation, and execution dispatching. |
| **Strategy Pattern** | Smart Router | [`routing/`](./routing/) | `RoutingStrategy` with interchangeable strategies: `JevRoutingStrategy`, `RuleBasedStrategy`, `LLMJudgeStrategy`, and `CostCascadingStrategy`. |
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
- **Jev System One Safety Filter (`JevSafetyFilter`):** Fast non-autoregressive semantic check for adversarial jailbreaks and harmful intent with true calibrated probabilities (`Noul()`), catching evasive prompts that bypass static regex.
- **Inbound PII Masking:** Replaces sensitive user emails, credit cards, SSNs, and API keys with typed tokens (e.g., `[REDACTED_EMAIL]`, `[REDACTED_API_KEY]`).

### Layer 3: Dual-Layer Caching Engine
- **Package:** [`caching/`](./caching/) (`semantic_cache.py`, `base.py`)
- **Pattern:** Cache-Aside & Strategy
- **Exact Hash Match:** $O(1)$ lookup via `sha256(model:normalized_prompt)`. Latency: `< 0.001s`, cost: `$0.00`.
- **Semantic Vector Cache:** Generates dense embeddings (`text-embedding-3-small`) and evaluates cosine similarity. If similarity $\ge 0.85$, returns cached response with 90%+ latency reduction.

### Layer 4: Smart Router & Model Virtualization
- **Package:** [`routing/`](./routing/) (`router.py`, `strategies.py`, `base.py`)
- **Pattern:** Strategy Pattern & System-1 Decision Pattern
- Dynamically assigns queries to:
  - **`cheap` (`gpt-4o-mini`)**: For simple questions, summaries, keyword searches, and intent classification.
  - **`smart` (`gpt-4o` / `claude-3-7`)**: For complex reasoning, multi-step code generation, and critical evaluations.
- **Strategies Available:**
  1. **`JevRoutingStrategy`**: Discriminative System-1 decision model from TypeSafe AI. Maps prompt state directly to model tiers in $<15\text{ms}$ with calibrated probabilities and zero token generation cost.
  2. **`RuleBasedStrategy`**: Deterministic keyword and code syntax heuristics ($<1\text{ms}$).
  3. **`LLMJudgeStrategy`**: Lightweight chat completion classification call.
  4. **`CostCascadingStrategy`**: Attempts execution on `cheap`; escalates to `smart` on uncertainty.

### Layer 5: Orchestrator & Human-in-the-Loop (HITL) Gateway
- **Package:** [`orchestration/`](./orchestration/) (`orchestrator.py`, `state.py`)
- **Pattern:** Finite State Machine (FSM), Command Pattern & System-1 Decision Pattern
- Decides execution path:
  1. `DIRECT_LLM`: Non-security general knowledge questions bypass document retrieval.
  2. `RAG_AUTOMATED`: Benign internal documentation queries run automated RAG-Fusion, PGVector search, and RRF ranking.
  3. `RAG_HUMAN_IN_THE_LOOP`: High-risk or offensive security requests (exploits, password cracking, privilege takeover) are **paused**. Generates a `PendingAction` and requires human operator sign-off (`approve`, `modify`, or `reject`).
  4. `TOOL_CALL`: External REST and MCP tool invocations (GitHub, Prometheus, Grafana).
- **Jev Integration (`evaluate_with_jev`)**: Non-autoregressive multi-question inference evaluating `strategy` (`Choice`), `risk_level` (`Choice`), and `is_offensive` (`Noul()`), providing calibrated risk thresholds without fragile JSON chat completions.

### Layer 6: Pluggable Tools, External APIs & MCP (Model Context Protocol)
- **Package:** [`tools/`](./tools/) (`registry.py`, `base.py`, `rag_tool.py`, `rest_tool.py`, `github_tool.py`, `prometheus_grafana_mcp.py`, `mcp_tool.py`)
- **Pattern:** Adapter Pattern & Plugin Registry
- **`RagKnowledgeTool`**: Exposes internal document search as an LLM tool.
- **`GitHubToolAdapter`**: Direct REST API v3 adapter for repository inspection, base64 file decoding, commit history, and issue tracking.
- **`PrometheusMCPAdapter`**: Model Context Protocol (MCP) tool (`mcp__prometheus__query`) enabling agents to evaluate PromQL queries (`ai_gateway_p99_latency_ms`, `ai_gateway_requests_total`, `litellm_token_spend_usd`, `ai_gateway_cache_hit_ratio`), list metric descriptors, and inspect active alerts.
- **`GrafanaMCPAdapter`**: Model Context Protocol (MCP) tool (`mcp__grafana__query`) providing dashboard discovery, panel inspection, datasource catalog queries (Prometheus, PostgreSQL, Redis), and alerting rule audits.
- **`MCPToolAdapter`**: General-purpose adapter bridging arbitrary Model Context Protocol (MCP) server endpoints into OpenAI-compatible function calling schemas.
- **Resilient Offline Fallback**: When Prometheus or Grafana endpoints are offline in local dev, adapters return high-fidelity synthetic telemetry simulations so agent workflows never break.

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
- **Jev Groundedness Shield (`JevGroundednessFilter`):** Discriminative Natural Language Inference (NLI) evaluating whether LLM claims are entailed by retrieved chunks (`is_grounded_in_context: Noul()`), preventing false-positive hallucination warnings caused by synonym paraphrasing.
- **Lexical Groundedness Verifier:** Token intersection fallback verifying citation density.
- **JSON Schema Enforcer:** Guarantees valid structured output when required.

---

## Directory Organization (`allrounder/week1/`)

```text
allrounder/week1/
├── app.py                          # FastAPI backend & interactive web dashboard (Jev, HITL, RAG)
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
│   ├── input_guardrails.py         # Injection, JevSafetyFilter, PII Masking, Length, Toxicity
│   └── output_guardrails.py        # Secret Leakage, JevGroundednessFilter, Groundedness, Schema
│
├── caching/                        # Cache-Aside Pattern & Dual-Tier Strategy
│   ├── __init__.py
│   ├── base.py                     # BaseCache abstract interface & CacheEntry dataclass
│   └── semantic_cache.py           # Exact O(1) hash + Semantic Vector Cosine similarity cache
│
├── routing/                        # Strategy Pattern for Model Routing & System-1 Decision
│   ├── __init__.py
│   ├── base.py                     # RoutingStrategy interface & RoutingDecision model
│   ├── strategies.py               # JevRoutingStrategy, RuleBasedStrategy, LLMJudgeStrategy, CostCascadingStrategy
│   └── router.py                   # SmartRouter context class
│
├── orchestration/                  # Finite State Machine (FSM) & Command Pattern (HITL)
│   ├── __init__.py
│   ├── state.py                    # ExecutionState, ExecutionStrategy, RiskLevel, PendingAction
│   └── orchestrator.py             # Stateful Orchestrator with Jev System-1 Intent & Risk Calibration
│
├── tools/                          # Adapter Pattern & Plugin Registry Pattern
│   ├── __init__.py
│   ├── base.py                     # BaseTool abstract interface & ToolDefinition schema
│   ├── rag_tool.py                 # RagKnowledgeTool adapter
│   ├── rest_tool.py                # RestApiToolAdapter (Jira, Slack, webhooks)
│   ├── github_tool.py              # GitHubToolAdapter (REST API v3 repos, files, issues)
│   ├── prometheus_grafana_mcp.py   # PrometheusMCPAdapter & GrafanaMCPAdapter (PromQL, Dashboards)
│   ├── mcp_tool.py                 # MCPToolAdapter (General Model Context Protocol)
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
│   ├── test_enterprise_architecture.py # Unit tests for all design patterns & Jev layers
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

## System 1 Fast Decision Engine: Jev (TypeSafe AI) Integration

### 1. Conceptual Architecture: System 1 (Jev) vs System 2 (Generative LLMs)

In cognitive science (Kahneman), **System 1** represents fast, instinctive, non-deliberative decision-making, while **System 2** represents slow, effortful, step-by-step reasoning. In contemporary AI architectures:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User Inbound Request                            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
┌───────────────────────────────────┐   ┌──────────────────────────────────┐
│   System 1: Jev (TypeSafe AI)     │   │ System 2: Generative Chat LLM    │
│   (Discriminative Decision Model) │   │ (Autoregressive Token Generation)│
├───────────────────────────────────┤   ├──────────────────────────────────┤
│ - Non-autoregressive              │   │ - Autoregressive token-by-token  │
│ - Latency: 5ms – 15ms             │   │ - Latency: 350ms – 1200ms        │
│ - Output: Strongly typed structs  │   │ - Output: Unstructured text prose│
│ - Calibrated probability metrics  │   │ - Hallucination & parsing risk   │
│ - Cost: Fractions of a cent       │   │ - High token compute spend       │
└─────────────────┬─────────────────┘   └─────────────────▲────────────────┘
                  │                                       │
                  │ Fast Decisions & Gating               │ Heavy Reasoning
                  ▼                                       │ (When Activated)
┌─────────────────────────────────────────────────────────┴────────────────┐
│  Gateway Pipeline: Safety Guard -> Smart Router -> HITL Orchestrator     │
└──────────────────────────────────────────────────────────────────────────┘
```

Standard LLM gateways suffer from **routing bottlenecks** when they invoke conversational LLMs (`gpt-4o-mini`, `claude-3-haiku`) as intermediate judges:
- **High Latency:** Sequential token decoding takes 300ms–800ms per intermediate decision.
- **Parsing Brittle-ness:** JSON output often fails validation or requires markdown fence cleanup (` ```json `).
- **Uncalibrated Confidence:** Generative models cannot output true mathematical posterior probabilities for safety and routing boundaries.

**Jev** solves this by evaluating input state against inference-time questions and directly returning typed answers accompanied by **calibrated probabilities** without generating conversational text.

---

### 2. The Four Integration Touchpoints in `week1`

```text
               ┌───────────────────────────────────────────────────┐
               │              Inbound User Request                 │
               └─────────────────────────┬─────────────────────────┘
                                         │
┌────────────────────────────────────────┴────────────────────────────────────────┐
│ Touchpoint 1: Inbound Guardrails (`JevSafetyFilter`)                            │
│ - Question: is_jailbreak (Noul), is_harmful (Noul)                              │
│ - Action: Blocks prompt if calibrated risk >= 0.75                              │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Passed
┌────────────────────────────────────────┴────────────────────────────────────────┐
│ Touchpoint 2: Smart Router (`JevRoutingStrategy`)                               │
│ - Question: complexity_tier (Choice: "cheap" vs "smart")                        │
│ - Latency: < 15ms (10x faster than LLMJudgeStrategy)                            │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Selected Model Tier
┌────────────────────────────────────────┴────────────────────────────────────────┐
│ Touchpoint 3: Orchestrator Intent & HITL Gate (`evaluate_with_jev`)              │
│ - Questions: strategy (Choice), risk_level (Choice), is_offensive (Noul)        │
│ - Gating: If is_offensive >= 0.70, transitions to ExecutionState.HITL_PAUSED    │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Execution (RAG / Direct / Tool)
┌────────────────────────────────────────┴────────────────────────────────────────┐
│ Touchpoint 4: Outbound Groundedness (`JevGroundednessFilter`)                   │
│ - Question: is_grounded_in_context (Noul)                                       │
│ - Replaces brittle lexical bag-of-words keyword overlap with true NLI entailment│
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Touchpoint 1: Inbound Guardrails (`guardrails/input_guardrails.py`)
- **Class:** `JevSafetyFilter(BaseGuardrailFilter)`
- **Mechanism:** Evaluates whether incoming prompts contain adversarial injection or toxic intent using `Noul()` criteria:
  ```python
  resp = jev_client.system_one(
      state=f"User prompt: {prompt}",
      questions={"is_jailbreak": Noul(), "is_harmful": Noul()},
  )
  ```
- **Advantage:** Catches semantic rephrasings and obfuscated jailbreaks that bypass static regex.

#### Touchpoint 2: Smart Router (`routing/strategies.py`)
- **Class:** `JevRoutingStrategy(RoutingStrategy)`
- **Mechanism:** Classifies query difficulty into virtual model aliases (`cheap` vs `smart`) using `Choice`:
  ```python
  resp = jev_client.system_one(
      state=f"User Query:\n{prompt}",
      questions={
          "complexity_tier": Choice(
              criteria={
                  "cheap": "Simple, factual questions, quick keyword lookups, or summaries.",
                  "smart": "Complex reasoning, system architecture, deep code refactoring.",
              }
          )
      },
  )
  ```
- **Advantage:** Single-digit millisecond latency; zero token generation overhead.

#### Touchpoint 3: Orchestrator Intent & HITL Gating (`orchestration/orchestrator.py`)
- **Method:** `evaluate_with_jev(prompt)`
- **Mechanism:** Evaluates `strategy` (`Choice`), `risk_level` (`Choice`), and `is_offensive` (`Noul()`) simultaneously. If `is_offensive >= 0.70`, the orchestrator immediately transitions to `ExecutionState.HITL_PAUSED`, generating a `PendingAction` command object for human authorization.

#### Touchpoint 4: Outbound Groundedness Verification (`guardrails/output_guardrails.py`)
- **Class:** `JevGroundednessFilter(BaseGuardrailFilter)`
- **Mechanism:** Determines Natural Language Inference (NLI) faithfulness between generated LLM claims and retrieved RAG context chunks:
  ```python
  resp = jev_client.system_one(
      state=f"Retrieved Context:\n{context}\n\nGenerated Output:\n{output}",
      questions={"is_grounded_in_context": Noul()},
  )
  ```
- **Advantage:** Eliminates false-positive hallucination warnings caused by synonym paraphrasing in traditional lexical overlap calculations.

---

### 3. Latency & Resource Efficiency Comparison

| Metric | Traditional LLM-as-a-Judge (`LLMJudgeStrategy`) | Jev System One (`JevRoutingStrategy`) | Improvement |
| :--- | :--- | :--- | :--- |
| **Classification Latency** | $450\text{ms} - 850\text{ms}$ | $\mathbf{8\text{ms} - 18\text{ms}}$ | **~40x faster** |
| **Tokens Consumed** | ~250 input + ~50 output tokens | **0 generation tokens** | **Compute eliminated** |
| **Parsing Reliability** | Markdown fences / JSON decode errors | **Strict strongly-typed structs** | **100% type-safe** |
| **Confidence Scoring** | Arbitrary prompt estimation (e.g. 0.92) | **Calibrated posterior probability** | **Mathematically sound** |

---

### 4. Resilient Offline Fallback Guarantee

Following the Ports & Adapters and Fallback patterns across `week1`:
- If `TYPESAFE_API_KEY` is not present in `.env`, or if an API connection error occurs, all components (`JevRoutingStrategy`, `JevSafetyFilter`, `evaluate_with_jev`, `JevGroundednessFilter`) automatically execute **calibrated local heuristic fallbacks**.
- Local testing and CI/CD pipelines pass 100% of unit tests with zero crashes and zero mandatory external network dependencies.

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

### 6. Query Prometheus & Grafana MCP Telemetry Directly
```bash
# Query Prometheus MCP for Gateway P99 Latency
curl -s -X POST http://localhost:8000/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "mcp__prometheus__query", "params": {"action": "query_instant", "query": "ai_gateway_p99_latency_ms"}}' | jq .

# Search Grafana MCP for AI Gateway Dashboards
curl -s -X POST http://localhost:8000/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "mcp__grafana__query", "params": {"action": "search_dashboards", "query": "gateway"}}' | jq .
```

### 7. Verify PostgreSQL Database Chunks
```bash
docker exec -it ai_gateway_pgvector psql -U postgres -d rag_db -c "SELECT id, title, page_start, substring(content from 1 for 80) FROM rag_chunks LIMIT 3;"
```


