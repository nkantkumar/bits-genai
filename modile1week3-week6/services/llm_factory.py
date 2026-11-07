from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from config import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    LLM_TEMPERATURE
)


def get_llm(
    provider: str,
    model: str
):

    provider = provider.lower().strip()

    if provider == "openai":

        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not configured"
            )

        return ChatOpenAI(
            model=model,
            api_key=OPENAI_API_KEY,
            temperature=LLM_TEMPERATURE
        )


    if provider == "anthropic":

        if not ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not configured"
            )

        return ChatAnthropic(
            model=model,
            api_key=ANTHROPIC_API_KEY,
            temperature=LLM_TEMPERATURE
        )


    raise ValueError(
        f"Unsupported provider: {provider}"
    )