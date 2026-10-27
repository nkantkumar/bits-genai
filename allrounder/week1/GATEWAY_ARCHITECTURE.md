# Multi-Layer Production AI Gateway Architecture

```
Internet / Clients
        │
        ▼ (Port 80/443/8080)
┌────────────────────────────────────────────────────────┐
│  Edge Reverse Proxy: Nginx / Caddy                     │
│  - TLS Termination (HTTPS certificates)                │
│  - IP-based DDoS Protection & Rate Limiting            │
│  - Large Payload Limits (50MB+ for vision / audio)     │
│  - SSE Buffering Disabled (proxy_buffering off)        │
│  - Edge Health Check (/healthz)                        │
└───────────────────────┬────────────────────────────────┘
                        │ HTTP / Internal Docker Network
                        ▼ (Port 4000)
┌────────────────────────────────────────────────────────┐
│  AI Gateway Layer: LiteLLM                             │
│  - Model Routing & Aliases ("cheap" vs "smart")        │
│  - Virtual API Key Auth & Team Budgets                 │
│  - Multi-Provider Fallbacks & Retries                  │
│  - Exact & Semantic Caching (Redis / In-memory)        │
│  - Spend & Latency Observability                       │
└───────────────────────┬────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│    OpenAI    │ │  Anthropic   │ │ Local Models │
│ (gpt-4o-mini)│ │(Claude 3.7)  │ │   (Ollama)   │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

## Why Both Nginx AND LiteLLM?

| Responsibility | Handled By Nginx / Caddy | Handled By LiteLLM |
| :--- | :--- | :--- |
| **TLS / SSL Termination** | ✅ Yes (Let's Encrypt, Certs) | ❌ No |
| **IP-Level Rate Limiting** | ✅ Yes (blocks DDoS at the OS/TCP edge) | ❌ No (LiteLLM rates by API key/user) |
| **Token Streaming (SSE)** | ✅ Yes (`proxy_buffering off;`) | ✅ Produces token streams |
| **Request Payload Size** | ✅ Yes (`client_max_body_size 50M`) | ❌ Relies on web server |
| **Model Routing & Fallbacks**| ❌ No (unaware of LLM semantics) | ✅ Yes (routes "cheap" vs "smart") |
| **LLM Spend & Token Budgets**| ❌ No | ✅ Yes (cost per key / user tracking) |
| **Semantic & Prompt Caching**| ❌ No | ✅ Yes (exact match & Redis cache) |

---

## Files in this Directory

- [`nginx.conf`](./nginx.conf): Local Nginx configuration (listening on port `8080`).
- [`Caddyfile`](./Caddyfile): Modern alternative with automatic HTTPS.
- [`nginx.docker.conf`](./nginx.docker.conf): Nginx configuration for Docker containers.
- [`docker-compose.gateway.yml`](./docker-compose.gateway.yml): Multi-container stack (Nginx + LiteLLM on an internal network).
- [`test_reverse_proxy.py`](./test_reverse_proxy.py): Python test suite validating completion, streaming, and rate-limiting.
- [`SmartRouter.py`](./SmartRouter.py): Dynamic complexity-based model router.

---

## How to Run

### Option 1: Local Nginx (Already verified on this machine)

1. **Start Nginx**:
   ```bash
   nginx -c $(pwd)/allrounder/week1/nginx.conf -p $(pwd)/allrounder/week1
   ```

2. **Reload / Stop Nginx**:
   ```bash
   # Reload after config edits
   nginx -c $(pwd)/allrounder/week1/nginx.conf -p $(pwd)/allrounder/week1 -s reload

   # Stop Nginx
   nginx -p $(pwd)/allrounder/week1 -s stop
   ```

3. **Run the Verification Suite**:
   ```bash
   python3 allrounder/week1/test_reverse_proxy.py
   ```

---

### Option 2: Docker Compose (Full Production Stack)

Run both Nginx and LiteLLM together where only Nginx is exposed on port `8080`:

```bash
docker compose -f allrounder/week1/docker-compose.gateway.yml up -d
```
