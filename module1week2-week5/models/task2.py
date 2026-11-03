from pydantic import BaseModel
from typing import Literal

class TaskRequest(BaseModel):

    task: Literal[
        "summarize",
        "rewrite",
        "headline",
        "keypoints"
    ]

    text: str



class TaskResponse(BaseModel):

    task: str
    result: str