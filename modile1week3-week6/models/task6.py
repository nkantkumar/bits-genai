from typing import Literal

from pydantic import BaseModel, ConfigDict


class TaskRequest(BaseModel):
    task: Literal[
        "summarize",
        "rewrite",
        "headline",
        "keypoints"
    ]
    text: str


class GuardrailStatus(BaseModel):
    status: Literal["passed", "failed"]
    reason: str


class GuardrailMetadata(BaseModel):
    input: GuardrailStatus
    output: GuardrailStatus


class CacheMetadata(BaseModel):
    hit: bool
    source: str
    latency_ms: float


class SummaryOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    summary: str


class RewriteOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    rewritten_text: str


class HeadlineOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    headline: str


class KeypointsOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    keypoints: list[str]


class TaskResponse(BaseModel):
    task: str
    provider: str
    model: str
    fallback_used: bool
    guardrails: GuardrailMetadata
    result: dict
    cache: CacheMetadata