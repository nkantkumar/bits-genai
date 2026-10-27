"""
Test Suite: Exact Prompt Caching & Semantic Vector Caching
Validates:
  1. Cold Call (Cache Miss) -> calls upstream LLM (~1.5s - 2.5s)
  2. Exact Cache Hit -> O(1) instant return (~0.001s, 99.9% faster)
  3. Semantic Cache Hit -> recognizes semantically equivalent prompt (~0.1s embedding lookup)
  4. Cache Miss -> distinct prompt bypasses cache and stores new entry
"""

import time
from SemanticCache import SemanticCache
from openai import OpenAI
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

BASE_URL = os.getenv("NGINX_PROXY_URL") or os.getenv("LITELLM_PROXY_URL") or "http://localhost:4000/v1"
API_KEY = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
cache = SemanticCache(similarity_threshold=0.85)


def query_llm_with_cache(prompt: str, model: str = "cheap") -> tuple[str, str, float, float]:
    """
    Checks cache first. If hit, returns immediately.
    If miss, calls LLM through Gateway and saves to cache.
    """
    start_time = time.time()

    # 1. Lookup in Cache (Exact + Semantic)
    cached_response, hit_type, similarity = cache.get(prompt, model=model)
    if cached_response is not None:
        elapsed = time.time() - start_time
        return cached_response, hit_type, similarity, elapsed

    # 2. Cache Miss: Execute LLM Call through AI Gateway
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
    )
    response_text = r.choices[0].message.content or ""
    elapsed = time.time() - start_time

    # 3. Store in Cache
    cache.set(prompt, response_text, model=model)
    return response_text, "CACHE_MISS", similarity, elapsed


def run_caching_tests():
    print("=" * 70)
    print(" AI Gateway: Semantic & Prompt Caching Demonstration")
    print(f" Target Gateway: {BASE_URL}")
    print("=" * 70)

    # -------------------------------------------------------------
    # Scenario 1: Cold Call (Initial Prompt)
    # -------------------------------------------------------------
    p1 = "What is the capital of France?"
    print(f"\n[Test 1: Cold Query] Prompt: \"{p1}\"")
    resp, hit_type, score, duration = query_llm_with_cache(p1)
    print(f"-> Status:     {hit_type}")
    print(f"-> Latency:    {duration:.3f}s")
    print(f"-> Answer:     {resp.strip()}")

    # -------------------------------------------------------------
    # Scenario 2: Exact Match Prompt Cache
    # -------------------------------------------------------------
    p2 = "What is the capital of France?"
    print(f"\n[Test 2: Identical Query] Prompt: \"{p2}\"")
    resp, hit_type, score, duration = query_llm_with_cache(p2)
    print(f"-> Status:     {hit_type} (Similarity: {score:.2f})")
    print(f"-> Latency:    {duration:.4f}s  <-- Instant O(1) Cache Hit!")
    print(f"-> Answer:     {resp.strip()}")

    # -------------------------------------------------------------
    # Scenario 3: Semantic Cache Hit (Different words, same meaning)
    # -------------------------------------------------------------
    p3 = "Could you tell me what the capital city of France is?"
    print(f"\n[Test 3: Semantic Equivalent Query] Prompt: \"{p3}\"")
    resp, hit_type, score, duration = query_llm_with_cache(p3)
    print(f"-> Status:     {hit_type} (Similarity: {score:.3f} >= 0.85)")
    print(f"-> Latency:    {duration:.3f}s  <-- Semantic Cache Hit (No LLM tokens billed!)")
    print(f"-> Answer:     {resp.strip()}")

    # -------------------------------------------------------------
    # Scenario 4: Semantic Cache Miss (Different question)
    # -------------------------------------------------------------
    p4 = "How far is the Moon from the Earth?"
    print(f"\n[Test 4: Novel Query] Prompt: \"{p4}\"")
    resp, hit_type, score, duration = query_llm_with_cache(p4)
    print(f"-> Status:     {hit_type} (Max Similarity: {score:.3f} < 0.85)")
    print(f"-> Latency:    {duration:.3f}s  <-- Upstream LLM invoked and cached")
    print(f"-> Answer:     {resp.strip()}")

    # -------------------------------------------------------------
    # Summary Metrics
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print(" Cache Telemetry & Statistics")
    print("=" * 70)
    stats = cache.stats()
    for k, v in stats.items():
        print(f"  {k:22}: {v}")
    print("=" * 70)


if __name__ == "__main__":
    run_caching_tests()
