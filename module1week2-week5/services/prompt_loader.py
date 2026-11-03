from pathlib import Path


PROMPT_DIR = Path("prompts")


def load_prompt(prompt_name: str) -> str:

    prompt_file = PROMPT_DIR / prompt_name

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Prompt not found: {prompt_file}"
        )

    return prompt_file.read_text(
        encoding="utf-8"
    )