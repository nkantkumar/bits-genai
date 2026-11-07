from services.prompt_loader import load_prompt


TASK_PROMPTS = {

    "summarize": "summarize_v1.txt",

    "keywords": "extract_keywords.txt",

    "headline": "headline.txt"
}


def route_task(task: str):

    task = task.lower().strip()

    if task not in TASK_PROMPTS:

        raise ValueError(
            f"Unsupported task: {task}"
        )

    prompt_name = TASK_PROMPTS[task]

    prompt = load_prompt(
        prompt_name
    )

    return {
        "task": task,
        "prompt_name": prompt_name,
        "prompt": prompt
    }