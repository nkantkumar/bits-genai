import os
import sys
import csv
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError, APIConnectionError


# ============================================================
# 1. Configuration
# ============================================================

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("Error: OPENAI_API_KEY not found in environment variables.")
    sys.exit(1)


client = OpenAI(api_key=api_key)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

PROMPT_DIR = Path("prompts")
TEST_DATA_FILE = Path("evaluation/rewrite_test_cases.csv")
REPORT_FILE = Path("evaluation/prompt_evaluation_report.csv")


# ============================================================
# 2. File utilities
# ============================================================

def load_prompt(prompt_name, **variables):
    """
    Load a prompt template and replace variables.
    """

    prompt_file = PROMPT_DIR / prompt_name

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_file}"
        )

    template = prompt_file.read_text(encoding="utf-8")

    return template.format(**variables)


def load_test_cases():
    """
    Load rewrite test cases from CSV.
    """

    if not TEST_DATA_FILE.exists():
        raise FileNotFoundError(
            f"Test data file not found: {TEST_DATA_FILE}"
        )

    with open(
        TEST_DATA_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return list(csv.DictReader(file))


# ============================================================
# 3. LLM call
# ============================================================

def call_llm(prompt):

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional business writing assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=200
        )

        return response

    except AuthenticationError:
        print("Authentication Error: Check your OPENAI_API_KEY.")
        sys.exit(1)

    except APIConnectionError:
        print("API Connection Error: Check your internet connection.")
        sys.exit(1)

    except Exception as e:
        print("LLM Error:", str(e))
        sys.exit(1)


# ============================================================
# 4. Run experiment
# ============================================================

def run_experiment(prompt_file, test_cases):

    results = []

    print("\n")
    print("=" * 70)
    print(f"Running experiment: {prompt_file}")
    print("=" * 70)

    for test_case in test_cases:

        test_id = test_case["id"]
        input_text = test_case["input_text"]

        prompt = load_prompt(
            prompt_file,
            text=input_text
        )

        response = call_llm(prompt)

        output = response.choices[0].message.content.strip()

        results.append({
            "id": test_id,
            "input": input_text,
            "output": output,
            "prompt": prompt_file
        })

        print(f"\nTest Case {test_id}")
        print("Input :", input_text)
        print("Output:", output)

    return results


# ============================================================
# 5. Simple formatting evaluation
# ============================================================

def evaluate_formatting(output):
    """
    Basic automated formatting checks.

    Returns 1 if the output passes all checks,
    otherwise 0.
    """

    score = 1

    # Output should not be empty
    if not output.strip():
        score = 0

    # Should be reasonably short
    if len(output.split()) > 50:
        score = 0

    # Should not contain obvious meta text
    unwanted_phrases = [
        "here is the rewritten sentence",
        "sure",
        "certainly",
        "the rewritten sentence is"
    ]

    output_lower = output.lower()

    for phrase in unwanted_phrases:
        if phrase in output_lower:
            score = 0

    return score


# ============================================================
# 6. Save evaluation report
# ============================================================

def save_report(results):

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        REPORT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        fieldnames = [
            "id",
            "prompt",
            "input",
            "output",
            "formatting_score"
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for result in results:

            result["formatting_score"] = evaluate_formatting(
                result["output"]
            )

            writer.writerow(result)

    print(f"\nEvaluation report saved to: {REPORT_FILE}")


# ============================================================
# 7. Main
# ============================================================

def main():

    test_cases = load_test_cases()

    print(f"Loaded {len(test_cases)} test cases.")

    # --------------------------------------------------------
    # Zero-shot experiment
    # --------------------------------------------------------

    zero_shot_results = run_experiment(
        "rewrite_zero_shot.txt",
        test_cases
    )

    # --------------------------------------------------------
    # Few-shot experiment
    # --------------------------------------------------------

    few_shot_results = run_experiment(
        "rewrite_few_shot.txt",
        test_cases
    )

    # --------------------------------------------------------
    # Combine results
    # --------------------------------------------------------

    all_results = (
        zero_shot_results +
        few_shot_results
    )

    save_report(all_results)


if __name__ == "__main__":
    main()