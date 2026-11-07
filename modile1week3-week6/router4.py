from services.prompt_loader import load_prompt
from services.model_selector import select_model


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
            f"Unsupported task: {task}"
        )

    # -------------------------------
    # Select prompt
    # -------------------------------

    config = TASK_CONFIG[task]

    prompt = load_prompt(
        config["prompt"]
    )


    # -------------------------------
    # Select model
    # -------------------------------

    model_config = select_model(task)


    return {

        "task": task,

        "prompt_name": config["prompt"],

        "prompt": prompt,

        "tier": model_config["tier"],

        "provider": model_config["provider"],

        "model": model_config["model"]
    }