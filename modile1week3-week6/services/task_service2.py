from langchain_core.prompts import PromptTemplate

from router3 import route_task
from services.llm_factory import get_llm


def execute_task(task: str, text: str):

    # -----------------------------------------
    # 1. Router selects task configuration
    # -----------------------------------------

    route = route_task(task)


    # -----------------------------------------
    # 2. Create prompt from selected template
    # -----------------------------------------

    prompt = PromptTemplate(
        template=route["prompt"],
        input_variables=["text"]
    )


    # -----------------------------------------
    # 3. Create LLM using provider abstraction
    # -----------------------------------------

    llm = get_llm(
        provider=route["provider"],
        model=route["model"]
    )


    # -----------------------------------------
    # 4. Build chain
    # -----------------------------------------

    chain = prompt | llm


    # -----------------------------------------
    # 5. Execute
    # -----------------------------------------

    response = chain.invoke({
        "text": text
    })


    # -----------------------------------------
    # 6. Return result
    # -----------------------------------------

    return {
        "task": route["task"],
        "provider": route["provider"],
        "model": route["model"],
        "result": response.content
    }