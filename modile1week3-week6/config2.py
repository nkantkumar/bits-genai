import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    # ========================================================
    # OpenAI
    # ========================================================

    OPENAI_API_KEY = os.getenv(
        "OPENAI_API_KEY"
    )


    # ========================================================
    # Primary Model
    # ========================================================

    PRIMARY_PROVIDER = os.getenv(
        "PRIMARY_PROVIDER",
        "openai"
    )

    PRIMARY_MODEL = os.getenv(
        "PRIMARY_MODEL",
        "gpt-4.1"
    )


    # ========================================================
    # Fallback Model
    # ========================================================

    FALLBACK_PROVIDER = os.getenv(
        "FALLBACK_PROVIDER",
        "openai"
    )

    FALLBACK_MODEL = os.getenv(
        "FALLBACK_MODEL",
        "gpt-4.1-mini"
    )


    # ========================================================
    # Resilience
    # ========================================================

    LLM_TIMEOUT = float(
        os.getenv(
            "LLM_TIMEOUT",
            "30"
        )
    )

    MAX_RETRIES = int(
        os.getenv(
            "MAX_RETRIES",
            "2"
        )
    )


    # ========================================================
    # Cache
    # ========================================================

    CACHE_DB = os.getenv(
        "CACHE_DB",
        "cache.db"
    )