"""
tests/test_reverse_proxy.py - Test Suite for Edge Reverse Proxy (Nginx) & Rate Limiting.
"""

import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

WEEK1_DIR = Path(__file__).resolve().parent.parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

load_dotenv(WEEK1_DIR.parent / ".env")
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
        model="cheap",
        messages=[
            {"role": "system", "content": "You are a concise AI assistant."},
            {"role": "user", "content": "Explain what a reverse proxy does in 2 sentences."},
        ],
        max_tokens=60,
    )
    elapsed = time.time() - start
    ans = response.choices[0].message.content
    print(f"[✓] Response Received in {elapsed:.2f}s:")
    print(f"    Model Used: {response.model}")
    print(f"    Answer: {ans.strip()}")


if __name__ == "__main__":
    if check_nginx_health():
        test_completion_through_nginx()
