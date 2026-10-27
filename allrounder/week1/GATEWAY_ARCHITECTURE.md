# Multi-Layer Production AI Gateway Architecture

```
Internet / Clients
        │
        ▼ (Port 80/443/8080)
┌────────────────────────────────────────────────────────┐
│  Layer 1: Edge Reverse Proxy (Nginx / Caddy)           │
│  - TLS Termination (HTTPS certificates)                │
│  - IP-based DDoS Protection & Rate Limiting            │
│  - Large Payload Limits (50MB+ for vision / audio)     │
│  - SSE Buffering Disabled (proxy_buffering off)        │
│  - Edge Health Check (/healthz)                        │
└───────────────────────┬────────────────────────────────┘
                        │ HTTP / Internal Docker Network
                        ▼ (Port 4000)
┌────────────────────────────────────────────────────────┐
│  Layer 2: AI Gateway (LiteLLM)                         │
│  - Model Routing & Aliases ("cheap" vs "smart")        │
│  - Virtual API Key Auth & Team Budgets                 │
│  - Multi-Provider Fallbacks & Retries                  │
│  - Spend & Latency Observability                       │
└───────────┬───────────────────────────────┬────────────┘
            │                               │
            │ Cache Check / Vectors         │ Upstream Fallback
            ▼ (Port 6379)                   ▼
┌────────────────────────────────┐  ┌──────────────────────────────┐
│  Layer 3: Vector & Prompt Cache│  │  Layer 4: LLM Providers      │
│  (Redis Stack / SemanticCache) │  │  - OpenAI (gpt-4o-mini)      │
│  - Exact Prompt Hash: O(1) 0ms │  │  - Anthropic (Claude 3.7)    │
│  - Semantic Vector Similarity: │  │  - Local Models (Ollama)     │
│    Cosine Similarity >= 0.80   │  └──────────────────────────────┘
└────────────────────────────────┘
```

---

## Dual-Layer Caching Explained

### 1. Exact Match Prompt Cache (O(1))
- **Mechanism**: Hashes the normalized prompt string and target model name: `sha256(model:normalized_prompt)`.
- **Performance**:
  - Latency: **< 0.001s (instantaneous)**.
  - Cost: **$0.00 (0 tokens billed upstream)**.
- **Use Case**: Repeated requests, identical instructions, automated polls, system prompts.

### 2. Semantic Vector Cache
- **Mechanism**:
  1. Computes dense vector embeddings using `text-embedding-3-small`.
  2. Compares vector cosine similarity against previous questions:
     $$\text{Similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$$
  3. If similarity exceeds the threshold (e.g. `similarity_threshold: 0.80`):
     Returns the cached answer immediately without generating a single LLM token!
- **Example**:
  - Original Query: *"What is the capital of Japan?"* $\rightarrow$ Answer: *"Tokyo"* (Cached)
  - New Query: *"Can you tell me Japan's capital city?"* $\rightarrow$ **Similarity: 0.81** $\ge$ 0.80 $\rightarrow$ **Semantic Cache Hit!**
- **Performance**:
  - Latency: **~0.2s** (embedding calculation only vs 2.5s+ for full generation).
  - Cost: **95%+ reduction** in upstream token spend.

---

## Files in this Directory

- [`SemanticCache.py`](./SemanticCache.py): Production dual-layer caching engine (Exact hash + Semantic cosine similarity).
- [`test_caching.py`](./test_caching.py): Comprehensive test suite validating cold queries, exact cache hits, and semantic cache hits.
- [`litellm_config.yaml`](./litellm_config.yaml): LiteLLM gateway configuration enabling `redis-semantic` caching.
- [`docker-compose.gateway.yml`](./docker-compose.gateway.yml): Production Docker stack uniting Nginx + LiteLLM + Redis Stack.
- [`SmartRouter.py`](./SmartRouter.py): Dynamic router with integrated semantic caching.
- [`nginx.conf`](./nginx.conf): Local Nginx configuration on port `8080`.
- [`nginx.docker.conf`](./nginx.docker.conf): Nginx configuration inside Docker.
- [`Caddyfile`](./Caddyfile): Modern alternative with automatic HTTPS.
- [`test_reverse_proxy.py`](./test_reverse_proxy.py): Validates Nginx edge rate limits and SSE token streaming.

---

## How to Run

### 1. Test Semantic & Prompt Caching Directly
```bash
python3 allrounder/week1/test_caching.py
```

### 2. Test Smart Router with Integrated Caching
```bash
python3 allrounder/week1/SmartRouter.py
```

### 3. Run the Complete Docker Stack (Nginx + LiteLLM + Redis Stack)
```bash
docker compose -f allrounder/week1/docker-compose.gateway.yml up -d
```
