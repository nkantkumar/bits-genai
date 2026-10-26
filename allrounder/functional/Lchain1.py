import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

from dotenv import load_dotenv
load_dotenv()

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


# 1. Define your target Pydantic model
class BookInfo(BaseModel):
    title: str = Field(description="The title of the book")
    author: str = Field(description="The author of the book")
    genre: str = Field(description="Primary genre or category")
    year_published: int = Field(description="Publication year")

# 2. Set up the parser with the model
parser = PydanticOutputParser(pydantic_object=BookInfo)

# 3. Inject the parser's format instructions into the prompt
prompt = PromptTemplate(
    template="Provide details about the requested book.\n{format_instructions}\nBook: {query}\n",
    input_variables=["query"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# 4. Chain the prompt, model, and parser together
llm = ChatOpenAI(model="gpt-4o", temperature=0)
chain = prompt | llm | parser

# 5. Invoke the chain
result = chain.invoke({"query": "Dune by Frank Herbert"})

print(result)
# Output: title='Dune' author='Frank Herbert' genre='Science Fiction' year_published=1965
print(type(result))
# Output: <class '__main__.BookInfo'>
