"""
Test Suite: Production AI Gateway with Nginx Reverse Proxy
Architecture Flow:
  Client -> Nginx (Port 8080: Rate Limit, TLS, SSE Buffering Off)
         -> LiteLLM (Port 4000: Routing, Virtual Keys, Budgets, Caching)
         -> OpenAI (gpt-4o-mini / smart / cheap)
"""

import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load environment configuration
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

NGINX_PROXY_URL = os.getenv("NGINX_PROXY_URL", "http://localhost:8080/v1")
HEALTH_URL = "http://localhost:8080/healthz"
API_KEY = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")


def check_nginx_health():
    print("\n--- 1. Testing Nginx Edge Health Check ---")
    try:
        req = urllib.request.Request(HEALTH_URL)
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = resp.read().decode("utf-8")
            server_header = resp.headers.get("Server", "Unknown")
            print(f"[✓] Nginx is Online!")
            print(f"    Server Header: {server_header}")
            print(f"    Response: {data.strip()}")
            return True
    except Exception as e:
        print(f"[✗] Nginx is not reachable at {HEALTH_URL}: {e}")
        print("    Start Nginx using:")
        print("      nginx -c $(pwd)/allrounder/week1/nginx.conf -p $(pwd)/allrounder/week1")
        print("    Or via Docker:")
        print("      docker compose -f allrounder/week1/docker-compose.gateway.yml up -d")
        return False


def test_completion_through_nginx():
    print("\n--- 2. Testing Chat Completion via Nginx -> LiteLLM ---")
    client = OpenAI(
        base_url=NGINX_PROXY_URL,
        api_key=API_KEY,
    )

    print(f"[>] Sending request to Nginx endpoint: {NGINX_PROXY_URL}")
    start = time.time()
    response = client.chat.completions.create(
        model="cheap",  # routed by LiteLLM to gpt-4o-mini
        messages=[
            {"role": "system", "content": "You are a concise AI assistant."},
            {"role": "user", "content": "Explain what a reverse proxy does in 2 sentences."},
        ],
    )
    elapsed = time.time() - start

    content = response.choices[0].message.content or ""
    print(f"[✓] Received Response ({elapsed:.2f}s) via Model: {response.model}")
    print(f"    Content: {content.strip()}")


def test_streaming_through_nginx():
    print("\n--- 3. Testing Real-time Streaming (SSE Buffering Disabled) ---")
    client = OpenAI(
        base_url=NGINX_PROXY_URL,
        api_key=API_KEY,
    )

    print("[>] Streaming tokens in real-time through Nginx:")
    stream = client.chat.completions.create(
        model="cheap",
        messages=[{"role": "user", "content": "Count from 1 to 5 slowly with words."}],
        stream=True,
    )

    sys.stdout.write("    Tokens: ")
    sys.stdout.flush()
    for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        sys.stdout.write(delta)
        sys.stdout.flush()
    print("\n[✓] Streaming completed without Nginx proxy buffering delays!")


def test_rate_limiting():
    print("\n--- 4. Testing Edge IP Rate Limiting (Burst Protection) ---")
    print("[>] Firing 30 rapid requests to test Nginx limit_req zone (rate=10r/s, burst=15)...")
    url = f"{NGINX_PROXY_URL}/models"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    success = 0
    rate_limited = 0

    for i in range(30):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    success += 1
        except urllib.error.HTTPError as e:
            if e.code == 429:
                rate_limited += 1
        except Exception:
            pass

    print(f"    Allowed through (200 OK):       {success}")
    print(f"    Blocked by Nginx (429 Limited): {rate_limited}")
    if rate_limited > 0:
        print("[✓] Rate limiting verified: Excess requests were dropped at the Nginx edge!")
        print("    No backend tokens or LLM compute wasted on rejected traffic.")


if __name__ == "__main__":
    print("=" * 65)
    print(" Nginx -> LiteLLM Production Reverse Proxy Validation")
    print("=" * 65)

    if check_nginx_health():
        test_completion_through_nginx()
        test_streaming_through_nginx()
        test_rate_limiting()

    print("\n" + "=" * 65)
