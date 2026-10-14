import os
import sys
from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError, APIConnectionError, APIError, RateLimitError

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY is not set in the environment variables. Please set it in your .env file.")
    sys.exit(1)

client = OpenAI(api_key=api_key)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

#the call

print("Sending prompt: 'What is generative AI in one sentence?'")

try:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Be concise."},
            {"role": "user", "content": "What is generative AI in one sentence?"}
        ],
        temperature=0.7,
        max_tokens=100,
    )

#response + errors
    print("Response:", response.choices[0].message.content)
    print("Token used:", response.usage.total_tokens)

except AuthenticationError:
    print("Authentication Error: Please check your OPENAI_API_KEY.")
except APIConnectionError:
    print("API Connection Error: Please check your internet connection.")
except Exception as e:
    print(f"An error occurred: {e}")