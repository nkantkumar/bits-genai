import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

from dotenv import load_dotenv
load_dotenv()

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


# 1. Define a tool with type hints and a clear docstring
@tool
def calculate_vat(price: float, rate: float = 0.20) -> float:
    """Calculate the tax amount on a given price using a tax rate."""
    return price * rate

llm = ChatOpenAI(model="gpt-4o-mini")

# 2. Bind the tool to the model
llm_with_tools = llm.bind_tools([calculate_vat])

# 3. Model decides if and how to call it based on user input
response = llm_with_tools.invoke("How much VAT is charged on a 150 dollar purchase at standard 20% rate?")

print(response.tool_calls)
# Output: [{'name': 'calculate_vat', 'args': {'price': 150, 'rate': 0.2}, 'id': '...'}]
