from langchain_core.prompts import PromptTemplate

from router5 import route_task

from services.llm_factory import get_llm
from services.guardrails import EditorialGuardrail
from services.output_validator import validate_output
from services.prompt_loader import load_prompt

guardrail = EditorialGuardrail()


def execute_task(task: str, text: str):


    # ========================================================
    # 1. Input Guardrail
    # ========================================================

    input_result = guardrail.validate_input(text)

    if not input_result.passed:

        raise ValueError(
            f"Input rejected: {input_result.reason}"
        )

    # ========================================================
    # 2. Route the task
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
    # 4. Select Model
    # ========================================================

    llm = get_llm(
        provider=route["provider"],
        model=route["model"]
    )


    # ========================================================
    # 5. Execute LLM
    # ========================================================

    chain = prompt | llm

    response = chain.invoke({
        "text": text
    })

    output = response.content
    

    # ========================================================
    # 6. Output Guardrail
    # ========================================================

    output_result = guardrail.validate_output(
        output
    )

    if not output_result.passed:

        raise ValueError(
            f"Output rejected: {output_result.reason}"
        )


    # ========================================================
    # 7. JSON + Pydantic Validation
    # ========================================================

    validated_output = validate_output(
        output,
        route["output_schema"]
    )


    # ========================================================
    # 8. Return validated response
    # ========================================================

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

        "result": validated_output.model_dump()
    }