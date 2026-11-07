from langchain_openai import ChatOpenAI

from config2 import Config


def get_llm(
    provider: str,
    model: str
):

    # ========================================================
    # OpenAI
    # ========================================================

    if provider == "openai":

        return ChatOpenAI(
            model=model,
            api_key=Config.OPENAI_API_KEY,
            temperature=0.1,
            timeout=Config.LLM_TIMEOUT,
            max_retries=0
        )


    # ========================================================
    # Future providers
    # ========================================================

    elif provider == "anthropic":

        raise NotImplementedError(
            "Anthropic provider will be implemented in "
            "the multi-provider lab."
        )


    elif provider == "bedrock":

        raise NotImplementedError(
            "AWS Bedrock provider will be implemented "
            "in the multi-provider lab."
        )


    else:

        raise ValueError(
            f"Unsupported provider: {provider}"
        )

#Fun exercise would be have multiple provider and their models here!!