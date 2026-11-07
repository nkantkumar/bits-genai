from typing import Literal

from pydantic import BaseModel, ConfigDict


# ============================================================
# Request Model
# ============================================================

class TaskRequest(BaseModel):
    task: Literal[
        "summarize",
        "rewrite",
        "headline",
        "keypoints"
    ]
    text: str


# ============================================================
# Guardrail Models
# ============================================================

class GuardrailStatus(BaseModel):
    status: Literal["passed", "failed"]
    reason: str


class GuardrailMetadata(BaseModel):
    input: GuardrailStatus
    output: GuardrailStatus


# ============================================================
# LLM Output Schemas
# ============================================================

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


# ============================================================
# Final API Response
# ============================================================

class TaskResponse(BaseModel):
    task: str
    provider: str
    model: str
    guardrails: GuardrailMetadata
    result: dict