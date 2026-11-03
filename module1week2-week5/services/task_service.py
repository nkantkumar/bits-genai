import os

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from router2 import route_task


load_dotenv()


MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1-mini"
)


llm = ChatOpenAI(
    model=MODEL,
    temperature=0.1
)


def execute_task(task: str, text: str):

    # ------------------------------------------
    # 1. Ask router to select the task
    # ------------------------------------------

    route = route_task(task)


    # ------------------------------------------
    # 2. Create prompt from selected template
    # ------------------------------------------

    prompt = PromptTemplate(
        template=route["prompt"],
        input_variables=["text"]
    )


    # ------------------------------------------
    # 3. Create task-specific chain
    # ------------------------------------------

    chain = prompt | llm


    # ------------------------------------------
    # 4. Execute
    # ------------------------------------------

    response = chain.invoke({
        "text": text
    })


    # ------------------------------------------
    # 5. Return result
    # ------------------------------------------

    return {
        "task": route["task"],
        "result": response.content
    }