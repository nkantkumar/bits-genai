from langchain_core.prompts import PromptTemplate

from router4 import route_task
from services.llm_factory import get_llm


def execute_task(task: str, text: str):

    route = route_task(task)


    prompt = PromptTemplate(
        template=route["prompt"],
        input_variables=["text"]
    )


    llm = get_llm(
        provider=route["provider"],
        model=route["model"]
    )


    chain = prompt | llm


    response = chain.invoke({
        "text": text
    })


    return {
        "task": route["task"],
        "model_tier": route["tier"],
        "provider": route["provider"],
        "model": route["model"],
        "result": response.content
    }