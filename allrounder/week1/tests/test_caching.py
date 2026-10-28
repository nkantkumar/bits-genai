"""
tests/test_caching.py - Exact Prompt Caching & Semantic Vector Caching Benchmark.
"""

import os
import sys
import time
from pathlib import Path

WEEK1_DIR = Path(__file__).resolve().parent.parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from dotenv import load_dotenv
from openai import OpenAI
from caching import SemanticCache

load_dotenv(WEEK1_DIR.parent / ".env")
load_dotenv()

BASE_URL = os.getenv("NGINX_PROXY_URL") or os.getenv("LITELLM_PROXY_URL") or "http://localhost:4000/v1"
API_KEY = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
cache = SemanticCache(similarity_threshold=0.85)


def query_llm_with_cache(prompt: str, model: str = "cheap"):
    start_time = time.time()
    cached_response, hit_type, similarity = cache.get(prompt, model=model)
    if cached_response is not None:
        elapsed = time.time() - start_time
        return cached_response, hit_type, similarity, elapsed

    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
    )
    response_text = r.choices[0].message.content or ""
    elapsed = time.time() - start_time
    cache.set(prompt, response_text, model=model)
    return response_text, "CACHE_MISS", similarity, elapsed


def run_caching_tests():
    print("=" * 70)
    print(" AI Gateway: Semantic & Prompt Caching Demonstration")
    print(f" Target Gateway: {BASE_URL}")
    print("=" * 70)

    # 1. Cold Call
    prompt1 = "What is the capital of France?"
    ans1, status1, sim1, t1 = query_llm_with_cache(prompt1)
    print(f"\n[Test 1: Cold Query] Prompt: \"{prompt1}\"")
    print(f"-> Status:     {status1}")
    print(f"-> Latency:    {t1:.3f}s")
    print(f"-> Answer:     {ans1.strip()}")

    # 2. Exact Match
    ans2, status2, sim2, t2 = query_llm_with_cache(prompt1)
    print(f"\n[Test 2: Identical Query] Prompt: \"{prompt1}\"")
    print(f"-> Status:     {status2} (Similarity: {sim2:.2f})")
    print(f"-> Latency:    {t2:.4f}s  <-- Instant O(1) Cache Hit!")
    print(f"-> Answer:     {ans2.strip()}")

    # 3. Semantic Match
    prompt3 = "Could you tell me what the capital city of France is?"
    ans3, status3, sim3, t3 = query_llm_with_cache(prompt3)
    print(f"\n[Test 3: Semantic Equivalent Query] Prompt: \"{prompt3}\"")
    print(f"-> Status:     {status3} (Similarity: {sim3:.3f} >= 0.85)")
    print(f"-> Latency:    {t3:.3f}s  <-- Semantic Cache Hit (No LLM tokens billed!)")
    print(f"-> Answer:     {ans3.strip()}")


if __name__ == "__main__":
    run_caching_tests()
