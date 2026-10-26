"""
LiteLLM AI Gateway Integration for LangChain (allrounder/functional)

LiteLLM Proxy is an open-source, high-performance AI Gateway that sits between
your application and 100+ LLMs (OpenAI, Anthropic, Bedrock, Ollama, Groq, etc.).

Key Benefits of LiteLLM Proxy:
1. Unified API: Call any model using OpenAI-compatible endpoints (/v1/chat/completions).
2. Load Balancing & Fallbacks: Automatically retry or switch models if one fails or rate limits.
3. Observability & Spend Tracking: Track cost, latency, and tokens per user/key.
4. Caching: Built-in exact and semantic caching (Redis / in-memory) to slash latency and costs.
5. Virtual Keys: Generate budget-limited API keys for teams or microservices.

Setup & Starting LiteLLM Proxy:
- Docker:
    docker run -p 4000:4000 ghcr.io/berriai/litellm:main-latest
- Or Python CLI:
    pip install 'litellm[proxy]'
    litellm --model gpt-4o-mini --port 4000
- Admin UI: http://localhost:4000/ui
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

# Ensure repository root is on sys.path for common utilities
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

# Load from allrounder/.env if present, otherwise default .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Optional structured logger from common module
try:
    from common.logger import get_logger
    logger = get_logger("litellm_gateway")
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("litellm_gateway")


# 1. Health & Model Discovery Helper
def check_litellm_proxy(
    base_url: str,
    api_key: Optional[str] = None,
    timeout: float = 2.0,
) -> Tuple[bool, List[str], Optional[str]]:
    """
    Checks if LiteLLM Proxy is running and queries registered models.
    Returns: (is_online, list_of_models, error_message)
    """
    # Normalize base URL (strip trailing /v1 if present for health check or append /v1/models)
    models_url = base_url.rstrip("/")
    if not models_url.endswith("/v1"):
        models_url += "/v1"
    models_url += "/models"

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(models_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id") for m in data.get("data", []) if "id" in m]
            return True, models, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return False, [], f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, [], str(e)


# 2. LiteLLM Gateway Client Factory
def create_gateway_llm(
    model: Optional[str] = None,
    gateway_url: Optional[str] = None,
    api_key: Optional[str] = None,
    user_id: str = "allrounder_user",
    headers: Optional[Dict[str, str]] = None,
    temperature: float = 0.0,
    **kwargs: Any,
) -> ChatOpenAI:
    """
    Creates a LangChain ChatOpenAI instance routed through LiteLLM Proxy.

    Configuration resolution:
    - Gateway URL: argument -> LITELLM_PROXY_URL -> AI_GATEWAY_URL -> default "http://localhost:4000/v1"
    - API Key: argument -> LITELLM_API_KEY -> OPENAI_API_KEY
    """
    endpoint = (
        gateway_url
        or os.getenv("LITELLM_PROXY_URL")
        or os.getenv("AI_GATEWAY_URL")
        or "http://localhost:4000/v1"
    )

    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    key = (
        api_key
        or os.getenv("LITELLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )

    if not key:
        raise ValueError(
            "API key not found. Please set LITELLM_API_KEY or OPENAI_API_KEY in your .env file."
        )

    # LiteLLM supports custom user tracking & metadata headers for spend attribution
    request_headers: Dict[str, str] = {
        "x-litellm-user-id": user_id,
        "x-litellm-metadata": json.dumps({"source": "allrounder-langchain"}),
    }
    if headers:
        request_headers.update(headers)

    logger.info(
        "Configuring LangChain with LiteLLM Proxy",
        gateway=endpoint,
        model=selected_model,
        user_id=user_id,
    )

    llm_kwargs: Dict[str, Any] = {
        "model": selected_model,
        "temperature": temperature,
        "base_url": endpoint,
        "api_key": key,
        "default_headers": request_headers,
        **kwargs,
    }

    return ChatOpenAI(**llm_kwargs)


# 3. Main Demonstration
def main():
    print("=" * 65)
    print(" LiteLLM AI Gateway with LangChain (allrounder/functional)")
    print("=" * 65)

    gateway_url = (
        os.getenv("LITELLM_PROXY_URL")
        or os.getenv("AI_GATEWAY_URL")
        or "http://localhost:4000/v1"
    )
    api_key = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    target_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    print(f"[>] Target LiteLLM Proxy: {gateway_url}")

    # Check LiteLLM Proxy connectivity
    is_online, available_models, error = check_litellm_proxy(gateway_url, api_key)

    if is_online:
        print("[✓] Connected to LiteLLM Proxy successfully!")
        if available_models:
            print(f"[✓] Available models in LiteLLM: {', '.join(available_models)}")
            if target_model not in available_models:
                print(f"    (Note: Using '{target_model}' — ensure it is mapped in LiteLLM)")
        else:
            print("[i] Connected, no custom models listed (using default pass-through)")
    else:
        print(f"[!] Warning: Unable to query LiteLLM Proxy models ({error})")
        print("    If LiteLLM is not running, start it using:")
        print("      docker run -p 4000:4000 ghcr.io/berriai/litellm:main-latest")
        print("    Or local CLI:")
        print("      litellm --model gpt-4o-mini --port 4000\n")

    # Initialize LangChain LLM connected to LiteLLM Proxy
    llm = create_gateway_llm(
        model=target_model,
        gateway_url=gateway_url,
        api_key=api_key,
        temperature=0.2,
    )

    # 4. Construct LCEL Chain: Prompt -> LiteLLM Proxy -> Output Parser
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert on AI infrastructure and API Gateways. "
            "Give clear, concise, high-impact bullet points.",
        ),
        ("human", "{question}"),
    ])

    chain = prompt | llm | StrOutputParser()

    question = "Why should production AI applications use LiteLLM Proxy as an AI Gateway?"
    print(f"\n[Prompt]: {question}\n")

    # 5. Invoke through LiteLLM Proxy
    start_time = time.time()
    try:
        response = chain.invoke({"question": question})
        elapsed = time.time() - start_time
        print(f"[Response from LiteLLM Proxy] ({elapsed:.2f}s):\n")
        print(response.strip())
    except Exception as e:
        print(f"[!] Execution failed through {gateway_url}: {e}")
        print("\n--> Fallback Option: Falling back to direct OpenAI endpoint...")
        fallback_llm = ChatOpenAI(
            model=target_model,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        fallback_chain = prompt | fallback_llm | StrOutputParser()
        res = fallback_chain.invoke({"question": question})
        print(f"[Direct OpenAI Fallback Response]:\n{res.strip()}")

    print("\n" + "=" * 65)


if __name__ == "__main__":
    main()
