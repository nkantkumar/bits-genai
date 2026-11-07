import time

from langchain_core.prompts import PromptTemplate

from router5 import route_task

from services.llm_factory import get_llm
from services.guardrails import EditorialGuardrail
from services.output_validator import validate_output
from services.prompt_loader import load_prompt
from services.cache import SQLiteCache


guardrail = EditorialGuardrail()

cache = SQLiteCache(
    db_path="cache.db"
)


def execute_task(task: str, text: str):

    # ========================================================
    # Start total request timer
    # ========================================================

    start_time = time.perf_counter()


    # ========================================================
    # 1. Input Guardrail
    # ========================================================

    input_result = guardrail.validate_input(text)

    if not input_result.passed:

        raise ValueError(
            f"Input rejected: {input_result.reason}"
        )


    # ========================================================
    # 2. Route Task
    # ========================================================

    route = route_task(task)


    # ========================================================
    # 3. Load Prompt
    # ========================================================

    prompt_template = load_prompt(
        route["prompt"]
    )


    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["text"]
    )


    # ========================================================
    # 4. Format Prompt
    # ========================================================

    formatted_prompt = prompt.format(
        text=text
    )


    # ========================================================
    # 5. Generate Cache Key
    # ========================================================

    cache_key = cache.generate_key(
        task=route["task"],
        model=route["model"],
        prompt=formatted_prompt
    )


    # ========================================================
    # 6. Cache Lookup
    # ========================================================

    cached_response = cache.get(
        cache_key
    )


    # ========================================================
    # CACHE HIT
    # ========================================================

    if cached_response is not None:

        latency_ms = (
            time.perf_counter() - start_time
        ) * 1000

        print(
            f"CACHE HIT | "
            f"Latency: {latency_ms:.2f} ms"
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


    # ========================================================
    # CACHE MISS
    # ========================================================

    print("CACHE MISS")


    # ========================================================
    # 7. Select Model
    # ========================================================

    llm = get_llm(
        provider=route["provider"],
        model=route["model"]
    )


    # ========================================================
    # 8. Execute LLM
    # ========================================================

    llm_start_time = time.perf_counter()

    chain = prompt | llm

    response = chain.invoke({
        "text": text
    })

    output = response.content

    llm_latency_ms = (
        time.perf_counter() - llm_start_time
    ) * 1000


    print(
        f"LLM Latency: "
        f"{llm_latency_ms:.2f} ms"
    )


    # ========================================================
    # 9. Output Guardrail
    # ========================================================

    output_result = guardrail.validate_output(
        output
    )

    if not output_result.passed:

        raise ValueError(
            f"Output rejected: {output_result.reason}"
        )


    # ========================================================
    # 10. JSON + Pydantic Validation
    # ========================================================

    validated_output = validate_output(
        output,
        route["output_schema"]
    )


    # ========================================================
    # 11. Calculate total latency
    # ========================================================

    total_latency_ms = (
        time.perf_counter() - start_time
    ) * 1000


    # ========================================================
    # 12. Build Response
    # ========================================================

    result = {

        "task": route["task"],

        "provider": route["provider"],

        "model": route["model"],

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
    # 13. Store in Cache
    # ========================================================

    cache.set(
        cache_key=cache_key,
        task=route["task"],
        model=route["model"],
        prompt=formatted_prompt,
        response=result
    )


    print(
        f"TOTAL LATENCY: "
        f"{total_latency_ms:.2f} ms"
    )


    return result