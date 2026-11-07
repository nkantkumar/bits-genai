from langchain_core.prompts import PromptTemplate

from router4 import route_task
from services.llm_factory import get_llm
from services.guardrails import EditorialGuardrail


guardrail = EditorialGuardrail()


def execute_task(task: str, text: str):

    # -----------------------------
    # 1. Input Guardrail
    # -----------------------------

    input_result = guardrail.validate_input(text)

    if not input_result.passed:
        raise ValueError(
            f"Input rejected: {input_result.reason}"
        )


    # -----------------------------
    # 2. Route Task
    # -----------------------------

    route = route_task(task)


    # -----------------------------
    # 3. Build Prompt
    # -----------------------------

    prompt = PromptTemplate(
        template=route["prompt"],
        input_variables=["text"]
    )


    # -----------------------------
    # 4. Select Model
    # -----------------------------

    llm = get_llm(
        provider=route["provider"],
        model=route["model"]
    )


    # -----------------------------
    # 5. Execute LLM
    # -----------------------------

    chain = prompt | llm

    response = chain.invoke({
        "text": text
    })

    output = response.content


    # -----------------------------
    # 6. Output Guardrail
    # -----------------------------

    output_result = guardrail.validate_output(output)

    if not output_result.passed:
        raise ValueError(
            f"Output rejected: {output_result.reason}"
        )


    # -----------------------------
    # 7. Return response + metadata
    # -----------------------------

    return {
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

        "result": output
    }