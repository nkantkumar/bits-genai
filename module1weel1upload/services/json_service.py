import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from models.summary import SummaryResponse


load_dotenv()


# --------------------------------------------------
# 1. Create LLM
# --------------------------------------------------

MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1-mini"
)

llm = ChatOpenAI(
    model=MODEL,
    temperature=0.1
)


# --------------------------------------------------
# 2. Create Pydantic Output Parser
# --------------------------------------------------

parser = PydanticOutputParser(
    pydantic_object=SummaryResponse
)


# --------------------------------------------------
# 3. Load prompt
# --------------------------------------------------

prompt_template = open(
    "prompts/structured_summary.txt",
    "r",
    encoding="utf-8"
).read()


# --------------------------------------------------
# 4. Create LangChain PromptTemplate
# --------------------------------------------------

prompt = PromptTemplate(
    template=prompt_template + """

{format_instructions}
""",
    input_variables=["text"],
    partial_variables={
        "format_instructions":
            parser.get_format_instructions()
    }
)


# --------------------------------------------------
# 5. Create chain
# --------------------------------------------------

chain = prompt | llm | parser


# --------------------------------------------------
# 6. Generate structured response
# --------------------------------------------------

def generate_structured_response(text):

    result = chain.invoke({
        "text": text
    })

    return result