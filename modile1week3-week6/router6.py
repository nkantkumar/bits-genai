from models.task6 import (
    SummaryOutput,
    RewriteOutput,
    HeadlineOutput,
    KeypointsOutput
)


TASK_CONFIG = {

    "summarize": {
        "prompt": "summarize_v5.txt",
        "provider": "openai",
        "output_schema": SummaryOutput
    },

    "rewrite": {
        "prompt": "rewrite_v4.txt",
        "provider": "openai",
        "output_schema": RewriteOutput
    },

    "headline": {
        "prompt": "headline_v4.txt",
        "provider": "openai",
        "output_schema": HeadlineOutput
    },

    "keypoints": {
        "prompt": "keypoints_v2.txt",
        "provider": "openai",
        "output_schema": KeypointsOutput
    }
}


def route_task(task: str):

    if task not in TASK_CONFIG:

        raise ValueError(
            f"Unsupported task: {task}"
        )

    config = TASK_CONFIG[task]

    return {
        "task": task,
        "prompt": config["prompt"],
        "provider": config["provider"],
        "output_schema": config["output_schema"]
    }