import time

from langchain_core.prompts import PromptTemplate

from router6 import route_task

from config2 import Config

from services.cache import SQLiteCache
from services.guardrails import EditorialGuardrail
from services.llm_factory2 import get_llm
from services.model_selector2 import select_models
from services.output_validator import validate_output
from services.prompt_loader import load_prompt
from services.retry_handler import call_with_retry


guardrail = EditorialGuardrail()

cache = SQLiteCache(
    db_path=Config.CACHE_DB
)


def execute_task(
    task: str,
    text: str
):

    request_start = time.perf_counter()


    # ========================================================
    # 1. INPUT GUARDRAIL
    # ========================================================

    input_result = guardrail.validate_input(
        text
    )

    if not input_result.passed:

        raise ValueError(
            f"Input rejected: "
            f"{input_result.reason}"
        )


    # ========================================================
    # 2. TASK ROUTER
    # ========================================================

    route = route_task(task)


    # ========================================================
    # 3. PROMPT MANAGER
    # ========================================================

    prompt_template_text = load_prompt(
        route["prompt"]
    )

    prompt = PromptTemplate(
        template=prompt_template_text,
        input_variables=["text"]
    )

    formatted_prompt = prompt.format(
        text=text
    )

    # ========================================================
    # 4. MODEL SELECTION
    # ========================================================

    models = select_models(
        task
    )

    primary = models["primary"]
    fallback = models["fallback"]


    print(
        f"Primary: "
        f"{primary['provider']}/"
        f"{primary['model']}"
    )

    print(
        f"Fallback: "
        f"{fallback['provider']}/"
        f"{fallback['model']}"
    )

    # ========================================================
    # 5. CACHE LOOKUP
    # ========================================================

    cache_key = cache.generate_key(
        task=route["task"],
        model=Config.PRIMARY_MODEL,
        prompt=formatted_prompt
    )

    cached_response = cache.get(
        cache_key
    )


    if cached_response is not None:

        latency_ms = (
            time.perf_counter()
            - request_start
        ) * 1000

        print(
            f"CACHE HIT | "
            f"{latency_ms:.2f} ms"
        )

        cached_response["cache"] = {
            "hit": True,
            "source": "sqlite",
            "latency_ms": round(
                latency_ms,
                2
            )
        }

        return cached_response


    print("CACHE MISS")





    # ========================================================
    # 6. PRIMARY MODEL
    # ========================================================

    model_used = primary["model"]
    provider_used = primary["provider"]

    fallback_used = False


    try:

        llm = get_llm(
            provider=primary["provider"],
            model=primary["model"]
        )

        response = call_with_retry(
            llm=llm,
            prompt=formatted_prompt,
            max_retries=Config.MAX_RETRIES
        )


    # ========================================================
    # 7. FALLBACK MODEL
    # ========================================================

    except Exception as primary_error:

        print(
            "\nPRIMARY MODEL FAILED"
        )

        print(
            f"Reason: {primary_error}"
        )

        print(
            "Switching to fallback..."
        )


        fallback_used = True

        model_used = fallback["model"]

        provider_used = fallback["provider"]


        try:

            fallback_llm = get_llm(
                provider=fallback["provider"],
                model=fallback["model"]
            )

            response = call_with_retry(
                llm=fallback_llm,
                prompt=formatted_prompt,
                max_retries=Config.MAX_RETRIES
            )


        except Exception as fallback_error:

            raise RuntimeError(
                "Both primary and fallback "
                "models failed.\n"
                f"Primary error: "
                f"{primary_error}\n"
                f"Fallback error: "
                f"{fallback_error}"
            )


    # ========================================================
    # 8. RAW OUTPUT
    # ========================================================

    output = response.content


    # ========================================================
    # 9. OUTPUT GUARDRAIL
    # ========================================================

    output_result = guardrail.validate_output(
        output
    )

    if not output_result.passed:

        raise ValueError(
            f"Output rejected: "
            f"{output_result.reason}"
        )


    # ========================================================
    # 10. JSON + PYDANTIC VALIDATION
    # ========================================================

    validated_output = validate_output(
        output,
        route["output_schema"]
    )


    # ========================================================
    # 11. TOTAL LATENCY
    # ========================================================

    total_latency_ms = (
        time.perf_counter()
        - request_start
    ) * 1000


    # ========================================================
    # 12. RESPONSE
    # ========================================================

    result = {

        "task": route["task"],

        "provider": provider_used,

        "model": model_used,

        "fallback_used": fallback_used,

        "guardrails": {

            "input": {
                "status": "passed",
                "reason": input_result.reason
            },

            "output": {
                "status": "passed",
                "reason": output_result.reason
            }
        },

        "result": validated_output.model_dump(),

        "cache": {

            "hit": False,

            "source": "llm",

            "latency_ms": round(
                total_latency_ms,
                2
            )
        }
    }


    # ========================================================
    # 13. CACHE STORE
    # ========================================================

    cache.set(
        cache_key=cache_key,
        task=route["task"],
        model=model_used,
        prompt=formatted_prompt,
        response=result
    )


    print(
        f"\nTOTAL LATENCY: "
        f"{total_latency_ms:.2f} ms"
    )


    return result