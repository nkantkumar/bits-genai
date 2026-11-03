from services.prompt_loader import load_prompt


TASK_CONFIG = {

    "summarize": {
        "prompt": "summarize_v4.txt"
    },

    "rewrite": {
        "prompt": "rewrite_v3.txt"
    },

    "headline": {
        "prompt": "headline_v3.txt"
    },

    "keypoints": {
        "prompt": "keypoints.txt"
    }
}


def route_task(task: str):

    task = task.lower().strip()

    if task not in TASK_CONFIG:

        raise ValueError(
            f"Unsupported task: {task}. "
            f"Supported tasks: "
            f"{', '.join(TASK_CONFIG.keys())}"
        )

    config = TASK_CONFIG[task]

    prompt = load_prompt(
        config["prompt"]
    )

    return {
        "task": task,
        "prompt_name": config["prompt"],
        "prompt": prompt
    }