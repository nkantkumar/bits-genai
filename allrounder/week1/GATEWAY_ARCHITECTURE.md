# Enterprise Multi-Layer Production AI Gateway Architecture

```
User / Web UI / Clients
        │
        ▼ (Port 8000 Web UI / Port 80/8080 API)
┌────────────────────────────────────────────────────────┐
│  Layer 1: Input Guardrails & Defenses                  │
│  - Prompt Injection & Jailbreak Blocking               │
│  - PII Detection & Safe Masking (Emails, Keys, Cards)  │
│  - Toxic / Malicious Intent Rejection                  │
│  - Payload & Character Length Protection               │
└───────────────────────┬────────────────────────────────┘
                        │ Sanitized Prompt
                        ▼
┌────────────────────────────────────────────────────────┐
│  Layer 2: Edge Reverse Proxy (Nginx / Caddy)           │
│  - TLS Termination (HTTPS certificates)                │
│  - IP-based DDoS Protection & Rate Limiting            │
│  - Large Payload Limits (50MB+ for vision / audio)     │
│  - SSE Buffering Disabled (proxy_buffering off)        │
│  - Edge Health Check (/healthz)                        │
└───────────────────────┬────────────────────────────────┘
                        │ HTTP / Internal Docker Network
                        ▼ (Port 4000)
┌────────────────────────────────────────────────────────┐
│  Layer 3: AI Gateway & Smart Router (LiteLLM)          │
│  - Model Routing ("cheap" vs "smart")                  │
│  - Virtual API Key Auth & Team Budgets                 │
│  - Multi-Provider Fallbacks & Retries                  │
│  - Spend & Latency Observability                       │
└───────────┬───────────────────────────────┬────────────┘
            │                               │
            │ Cache Check / Vectors         │ Upstream Fallback
            ▼ (Port 6379)                   ▼
┌────────────────────────────────┐  ┌──────────────────────────────┐
│  Layer 4: Vector & Prompt Cache│  │  Layer 5: LLM Providers      │
│  (Redis Stack / SemanticCache) │  │  - OpenAI (gpt-4o-mini)      │
│  - Exact Prompt Hash: O(1) 0ms │  │  - Anthropic (Claude 3.7)    │
│  - Semantic Vector Similarity: │  │  - Local Models (Ollama)     │
│    Cosine Similarity >= 0.80   │  └──────────────────────────────┘
└────────────────────────────────┘
```

---

## Defensive Shields & Guardrails

| Guardrail Shield | Detection Mechanism | Action Taken |
| :--- | :--- | :--- |
| **Prompt Injection** | Heuristic & pattern matching (`ignore previous instructions`, `DAN`, `developer mode`, `reveal secret instructions`) | **BLOCKED** at the edge in `< 1ms` with 0 tokens billed |
| **PII Protection** | Regular expression detection for Emails, Phone Numbers, API Keys (`sk-...`, `ghp_...`), Credit Cards, SSNs | **MASKED** (`[REDACTED_EMAIL]`, `[REDACTED_API_KEY]`) or **BLOCKED** |
| **Toxicity & Threats**| Detects malicious requests (exploits, weapons, malware instructions) | **BLOCKED** |
| **Payload Overflow** | Max character limits (protects against token exhaustion attacks) | **BLOCKED** |

---

## Dual-Layer Caching

### 1. Exact Match Prompt Cache ($O(1)$)
- **Mechanism**: Hashes normalized prompt strings: `sha256(model:normalized_prompt)`.
- **Latency**: **`< 0.001s` (instantaneous)**.
- **Cost**: **$0.00 (0 tokens billed upstream)**.

### 2. Semantic Vector Cache
- **Mechanism**: Calculates dense vector embeddings with `text-embedding-3-small` and performs cosine similarity comparison.
- **Threshold**: Similarity $\ge 0.80$ returns the cached response even if phrased differently!
  - Query A: *"What is the capital of Japan?"* $\rightarrow$ Tokyo
  - Query B: *"Can you tell me Japan's capital city?"* $\rightarrow$ **Similarity: 0.81** $\rightarrow$ **Semantic Cache Hit!**
- **Latency**: **`~0.2s`** (90%+ latency reduction).

---

## Directory Organization (`allrounder/week1/`)

| File | Purpose |
| :--- | :--- |
| [`InputGuardrails.py`](./InputGuardrails.py) | Enterprise defensive input validation (Prompt Injection, PII, Toxicity). |
| [`SemanticCache.py`](./SemanticCache.py) | Dual-layer exact hash + semantic vector caching engine. |
| [`SmartRouter.py`](./SmartRouter.py) | Dynamic difficulty router integrating Guardrails $\to$ Cache $\to$ Gateway. |
| [`app.py`](./app.py) | FastAPI backend serving the interactive Web UI and `/api/chat` endpoint. |
| [`litellm_config.yaml`](./litellm_config.yaml) | LiteLLM gateway configuration with model lists and Redis semantic cache. |
| [`docker-compose.gateway.yml`](./docker-compose.gateway.yml) | Multi-container stack (Nginx + LiteLLM + Redis Stack). |
| [`nginx.conf`](./nginx.conf) / [`nginx.docker.conf`](./nginx.docker.conf) | Nginx reverse proxy configurations with rate limits & SSE streaming. |
| [`Caddyfile`](./Caddyfile) | Caddy reverse proxy alternative with auto-HTTPS. |
| [`test_caching.py`](./test_caching.py) | Unit tests verifying exact vs semantic cache hits. |
| [`test_reverse_proxy.py`](./test_reverse_proxy.py) | Unit tests verifying Nginx proxy routing, streaming, and rate-limits. |

---

## How to Run

### 1. Interactive Web Dashboard
Run the web application to submit any prompt, test PII masking, injections, and inspect live pipeline traces:
```bash
python3 -m uvicorn allrounder.week1.app:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser.

### 2. CLI Smart Router with Guardrails & Caching
```bash
python3 allrounder/week1/SmartRouter.py
```

### 3. Run Cache Benchmarks
```bash
python3 allrounder/week1/test_caching.py
```

### 4. Run Docker Gateway Stack
```bash
docker compose -f allrounder/week1/docker-compose.gateway.yml up -d
```
