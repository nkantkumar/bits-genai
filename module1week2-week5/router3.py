from services.prompt_loader import load_prompt


TASK_CONFIG = {

    "summarize": {
        "prompt": "summarize_v4.txt",
        "provider": "openai",
        "model": "gpt-4.1-mini"
    },

    "rewrite": {
        "prompt": "rewrite_v3.txt",
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001"
    },

    "headline": {
        "prompt": "headline_v3.txt",
        "provider": "openai",
        "model": "gpt-4.1-mini"
    },

    "keypoints": {
        "prompt": "keypoints.txt",
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001"
    }
}


def route_task(task: str):

    task = task.lower().strip()

    if task not in TASK_CONFIG:
        raise ValueError(
            f"Unsupported task: {task}. "
            f"Supported tasks: {', '.join(TASK_CONFIG.keys())}"
        )

    config = TASK_CONFIG[task]

    prompt = load_prompt(
        config["prompt"]
    )

    return {
        "task": task,
        "prompt_name": config["prompt"],
        "prompt": prompt,
        "provider": config["provider"],
        "model": config["model"]
    }