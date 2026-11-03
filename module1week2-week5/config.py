import os
from dotenv import load_dotenv

load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

LLM_TEMPERATURE = float(
    os.getenv("LLM_TEMPERATURE", "0.1")
)