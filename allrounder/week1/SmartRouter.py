"""
Route simple prompts to a cheap model and hard prompts to a frontier model,
both through one LiteLLM proxy.

Setup:
    pip install openai
    litellm --config config.yaml          # proxy on http://localhost:4000
    export LITELLM_API_KEY="sk-1234"      # your proxy key
    export LITELLM_BASE_URL="http://localhost:4000"

Model aliases "cheap" and "smart" are defined in the proxy's config.yaml.
"""
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Ensure week1 is on sys.path for local module imports
WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from SemanticCache import SemanticCache

# Initialize Semantic & Prompt Cache (threshold 0.80 for semantic similarity)
router_cache = SemanticCache(similarity_threshold=0.80)

# Load environment variables (.env from allrounder or root)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

base_url = (
    os.getenv("NGINX_PROXY_URL")
    or os.getenv("LITELLM_PROXY_URL")
    or os.getenv("AI_GATEWAY_URL")
    or "http://localhost:4000/v1"
)
api_key = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")

if not api_key:
    raise EnvironmentError("Neither LITELLM_API_KEY nor OPENAI_API_KEY is configured in your .env file.")

client = OpenAI(api_key=api_key, base_url=base_url)

CHEAP = "cheap"   # e.g. local Llama / gpt-4o-mini
SMART = "smart"   # e.g. a frontier model

HARD_HINTS = re.compile(
    r"\b(analy[sz]e|prove|derive|debug|refactor|architecture|trade-?offs?|"
    r"step[- ]by[- ]step|compare|optimi[sz]e|legal|contract|diagnos\w*)\b",
    re.IGNORECASE,
)


# --- Strategy 1: cheap rule-based router (free, instant) --------------------
def classify_by_rules(prompt: str) -> str:
    score = 0
    if len(prompt.split()) > 120:
        score += 1
    if "```" in prompt or "def " in prompt or "class " in prompt:
        score += 1
    if HARD_HINTS.search(prompt):
        score += 1
    if prompt.count("?") > 1:
        score += 1
    return SMART if score >= 2 else CHEAP


# --- Strategy 2: let the cheap model judge difficulty (costs one tiny call) --
def classify_by_llm(prompt: str) -> str:
    r = client.chat.completions.create(
        model=CHEAP,
        max_tokens=5,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "Classify the user's task as SIMPLE (lookup, short rewrite, "
                "formatting, small talk) or HARD (multi-step reasoning, coding, "
                "analysis, high-stakes). Reply with one word: SIMPLE or HARD.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    verdict = (r.choices[0].message.content or "").strip().upper()
    return SMART if "HARD" in verdict else CHEAP


# --- Strategy 3: cascade (try cheap first, escalate if it gives up) ---------
def ask_with_cascade(prompt: str) -> tuple[str, str]:
    r = client.chat.completions.create(
        model=CHEAP,
        messages=[
            {
                "role": "system",
                "content": "Answer the question. If you are not confident you can answer "
                "correctly, reply with exactly the single word ESCALATE.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    text = (r.choices[0].message.content or "").strip()
    if text == "ESCALATE" or r.choices[0].finish_reason == "length":
        r = client.chat.completions.create(
            model=SMART, messages=[{"role": "user", "content": prompt}]
        )
        text = r.choices[0].message.content or ""
    return text, r.model


# --- Main entry point (With Semantic & Prompt Caching) ----------------------
def ask(prompt: str, strategy: str = "rules", use_cache: bool = True) -> tuple[str, str]:
    # 1. Check Cache First (Saves classification & LLM call if similar query exists)
    if use_cache:
        cached_resp, hit_type, score = router_cache.get(prompt, model="router")
        if cached_resp is not None:
            return cached_resp, f"cache ({hit_type}, sim={score:.2f})"

    # 2. Cache Miss: Execute Router
    if strategy == "cascade":
        answer, model_used = ask_with_cascade(prompt)
    else:
        chosen = classify_by_llm(prompt) if strategy == "llm" else classify_by_rules(prompt)
        r = client.chat.completions.create(
            model=chosen, messages=[{"role": "user", "content": prompt}]
        )
        answer, model_used = r.choices[0].message.content or "", r.model

    # 3. Save to Cache for subsequent exact or semantic queries
    if use_cache:
        router_cache.set(prompt, answer, model="router")

    return answer, model_used


if __name__ == "__main__":
    print(f"[Gateway]: LiteLLM proxy at {base_url}\n")

    prompts = [
        # Query 1: Cold call (cheap)
        "What is the capital of Japan?",
        # Query 2: Exact Repeat -> Prompt Cache Hit (0ms)
        "What is the capital of Japan?",
        # Query 3: Semantic Equivalent -> Semantic Cache Hit
        "Can you tell me Japan's capital city?",
        # Query 4: Cold call (smart)
        "Analyze the trade-offs between microservices and a monolith for a 5-person "
        "startup, step by step, and recommend an architecture. Why? What would change at 50 people?",
    ]
    for p in prompts:
        answer, model_used = ask(p, strategy="rules")
        print(f"Q: {p[:60]}...")
        print(f"-> routed to: {model_used}")
        print(f"A: {answer[:120]}...\n")