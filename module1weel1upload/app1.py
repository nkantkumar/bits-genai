import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError, APIConnectionError

# --------------------------------------------------
# 1. Load environment variables
# --------------------------------------------------

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("Error: OPENAI_API_KEY not found in environment variables.")
    sys.exit(1)

# --------------------------------------------------
# 2. Initialize OpenAI client
# --------------------------------------------------

client = OpenAI(api_key=api_key)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# --------------------------------------------------
# 3. File locations
# --------------------------------------------------

PROMPT_DIR = Path("prompts")
TEXT_FILE = Path("long_text.txt")

# --------------------------------------------------
# 4. Load input text
# --------------------------------------------------

def load_text(file_path):
    """Read text from a file."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Text file not found: {file_path}"
        )

    return file_path.read_text(encoding="utf-8").strip()

# --------------------------------------------------
# 5. Load prompt template
# --------------------------------------------------

def load_prompt(prompt_name, **variables):
    """
    Load a prompt template from the prompts/ directory
    and replace template variables.
    """

    prompt_file = PROMPT_DIR / prompt_name

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_file}"
        )

    template = prompt_file.read_text(encoding="utf-8")

    return template.format(**variables)

# --------------------------------------------------
# 6. Call LLM
# --------------------------------------------------

def call_llm(prompt):

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=100
        )

        return response

    except AuthenticationError:
        print("Authentication Error: Please check your OPENAI_API_KEY.")
        sys.exit(1)

    except APIConnectionError:
        print("API Connection Error: Please check your internet connection.")
        sys.exit(1)

    except Exception as e:
        print("An error occurred:", str(e))
        sys.exit(1)

# --------------------------------------------------
# 7. Main application
# --------------------------------------------------

try:

    # Load input text from external file
    text = load_text(TEXT_FILE)

    print(f"Loaded text from: {TEXT_FILE}")
    print(f"Characters: {len(text)}")


    # --------------------------------------------------
    # Summarization
    # --------------------------------------------------

    summarize_prompt = load_prompt(
        "summarize_v2.txt",
        text=text
    )

    print("\n--- SUMMARIZATION PROMPT ---")
    print(summarize_prompt)

    response = call_llm(summarize_prompt)

    print("\n--- SUMMARY ---")
    print(response.choices[0].message.content)

    # --------------------------------------------------
    # Keyword extraction
    # --------------------------------------------------

    keyword_prompt = load_prompt(
        "extract_keywords.txt",
        text=text
    )

    print("\n--- KEYWORD PROMPT ---")
    print(keyword_prompt)

    response = call_llm(keyword_prompt)

    print("\n--- KEYWORDS ---")
    print(response.choices[0].message.content)


    # --------------------------------------------------
    # Headline generation
    # --------------------------------------------------

    headline_prompt = load_prompt(
        "headline.txt",
        text=text
    )

    print("\n--- HEADLINE PROMPT ---")
    print(headline_prompt)

    response = call_llm(headline_prompt)

    print("\n--- HEADLINE ---")
    print(response.choices[0].message.content)

    

except FileNotFoundError as e:
    print(f"File Error: {e}")
    sys.exit(1)

