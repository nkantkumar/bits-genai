from typing import Literal
from pydantic import BaseModel


class TaskRequest(BaseModel):
    task: str
    text: str


class GuardrailStatus(BaseModel):
    status: Literal["passed", "failed"]
    reason: str


class GuardrailMetadata(BaseModel):
    input: GuardrailStatus
    output: GuardrailStatus


class TaskResponse(BaseModel):
    task: str
    provider: str
    model: str
    guardrails: GuardrailMetadata
    result: str