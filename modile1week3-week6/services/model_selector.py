MODEL_CONFIG = {

    "small": {
        "provider": "openai",
        "model": "gpt-4.1-mini"
    },

    "large": {
        "provider": "openai",
        "model": "gpt-4.1"
    }
}


TASK_MODEL_RULES = {

    "summarize": "small",

    "headline": "small",

    "keypoints": "small",

    "rewrite": "large"
}


def select_model(task: str):

    task = task.lower().strip()

    if task not in TASK_MODEL_RULES:

        raise ValueError(
            f"No model selection rule "
            f"defined for task: {task}"
        )

    tier = TASK_MODEL_RULES[task]

    config = MODEL_CONFIG[tier]

    return {
        "tier": tier,
        "provider": config["provider"],
        "model": config["model"]
    }