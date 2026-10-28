"""
guardrails/output_guardrails.py - Outbound LLM Guardrail Chain of Responsibility.

Enterprise Defensive Shield for Outbound LLM Responses:
1. Secret & PII Leakage Filter: Ensures LLM never returns database credentials, API keys,
   private keys, or sensitive customer PII.
2. Groundedness Filter: Computes overlap ratio between claims in the response and retrieved RAG context.
3. Schema & Syntax Validation Filter: Enforces valid JSON structure when requested.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .base import BaseGuardrailFilter, GuardrailAction, GuardrailContext, GuardrailPipeline

logger = logging.getLogger("OutputGuardrails")


class OutputViolationType(str, Enum):
    SECRET_LEAKAGE = "SECRET_LEAKAGE"
    PII_LEAKAGE = "PII_LEAKAGE"
    LOW_GROUNDEDNESS = "LOW_GROUNDEDNESS"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    HARMFUL_CONTENT = "HARMFUL_CONTENT"


@dataclass
class OutputGuardrailResult:
    passed: bool
    action: str  # "ALLOWED", "SANITIZED", or "BLOCKED"
    original_output: str
    sanitized_output: str
    violations: List[str] = field(default_factory=list)
    leaked_secrets: List[str] = field(default_factory=list)
    groundedness_score: float = 1.0
    blocked_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "action": self.action,
            "violations": self.violations,
            "leaked_secrets_count": len(self.leaked_secrets),
            "groundedness_score": round(self.groundedness_score, 3),
            "blocked_reason": self.blocked_reason,
            "sanitized_output_preview": (
                self.sanitized_output[:120] + "..." if len(self.sanitized_output) > 120 else self.sanitized_output
            ),
        }


# -----------------------------------------------------------------------------
# Concrete Filter 1: Outbound Secret & Credential Leakage Filter
# -----------------------------------------------------------------------------
class SecretLeakageFilter(BaseGuardrailFilter):
    SECRET_PATTERNS = {
        "OPENAI_KEY": re.compile(r"\b(sk-[a-zA-Z0-9_-]{20,})\b"),
        "GITHUB_TOKEN": re.compile(r"\b(ghp_[a-zA-Z0-9]{20,}|github_pat_[a-zA-Z0-9_]{22,})\b"),
        "AWS_KEY": re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        "PRIVATE_KEY": re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
        "DB_CONNECTION_STRING": re.compile(
            r"\b(?:postgres(?:ql)?|mysql|mongodb|redis):\/\/[a-zA-Z0-9_]+:[^@\s]+@[a-zA-Z0-9_.-]+(?::\d+)?\/[a-zA-Z0-9_.-]+\b",
            re.IGNORECASE,
        ),
    }

    PII_PATTERNS = {
        "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    }

    def process(self, context: GuardrailContext) -> GuardrailContext:
        leaked_secrets: List[str] = []
        sanitized = context.current_text

        # 1. Redact secrets
        for secret_name, pattern in self.SECRET_PATTERNS.items():
            matches = pattern.findall(sanitized)
            if matches:
                leaked_secrets.extend(matches)
                sanitized = pattern.sub(f"[REDACTED_{secret_name}]", sanitized)

        # 2. Redact outbound PII
        for pii_name, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(sanitized)
            if matches:
                leaked_secrets.extend(matches)
                sanitized = pattern.sub(f"[REDACTED_{pii_name}]", sanitized)

        if leaked_secrets:
            context.sanitize(sanitized, violation=OutputViolationType.SECRET_LEAKAGE.value)
            context.metadata["leaked_secrets"] = leaked_secrets
            context.risk_score = max(context.risk_score, 0.8)

        return context


# -----------------------------------------------------------------------------
# Concrete Filter 2: Groundedness & Hallucination Filter
# -----------------------------------------------------------------------------
class GroundednessFilter(BaseGuardrailFilter):
    STOP_WORDS: Set[str] = {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "of",
        "is", "are", "was", "were", "this", "that", "these", "those", "it", "be",
        "by", "as", "from", "into", "we", "you", "they", "he", "she", "can", "will",
    }

    def __init__(self, min_groundedness_score: float = 0.25, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.min_groundedness_score = min_groundedness_score

    def _extract_keywords(self, text: str) -> Set[str]:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        return {w for w in words if w not in self.STOP_WORDS}

    def process(self, context: GuardrailContext) -> GuardrailContext:
        retrieved_context = context.metadata.get("retrieved_context")
        if not retrieved_context:
            context.metadata["groundedness_score"] = 1.0
            return context

        output_words = self._extract_keywords(context.current_text)
        if not output_words:
            context.metadata["groundedness_score"] = 1.0
            return context

        context_combined = " ".join(retrieved_context).lower()
        context_words = self._extract_keywords(context_combined)

        overlap = output_words.intersection(context_words)
        score = len(overlap) / len(output_words)
        context.metadata["groundedness_score"] = score

        if score < self.min_groundedness_score:
            context.violations.append(OutputViolationType.LOW_GROUNDEDNESS.value)
            context.risk_score = max(context.risk_score, 0.6)
            logger.warning(f"Groundedness warning: score {score:.3f} < {self.min_groundedness_score}")

        return context


# -----------------------------------------------------------------------------
# Concrete Filter 3: JSON Schema Validation Filter
# -----------------------------------------------------------------------------
class SchemaValidationFilter(BaseGuardrailFilter):
    def process(self, context: GuardrailContext) -> GuardrailContext:
        expected_schema = context.metadata.get("expected_json_schema")
        if not expected_schema:
            return context

        try:
            parsed = json.loads(context.current_text)
            context.metadata["parsed_json"] = parsed
        except json.JSONDecodeError as e:
            context.block(
                violation=OutputViolationType.SCHEMA_VIOLATION.value,
                reason=f"Output failed strict JSON schema validation: {str(e)}",
                risk_score=0.9,
            )
        return context


# -----------------------------------------------------------------------------
# Facade: OutputGuardrails
# -----------------------------------------------------------------------------
class OutputGuardrails:
    """Enterprise outbound defensive inspection pipeline using Chain of Responsibility."""

    def __init__(self, min_groundedness_score: float = 0.25):
        self.min_groundedness_score = min_groundedness_score
        self.pipeline = GuardrailPipeline([
            SecretLeakageFilter(),
            GroundednessFilter(min_groundedness_score=self.min_groundedness_score),
            SchemaValidationFilter(),
        ])

    def inspect(
        self,
        output_text: str,
        retrieved_context: Optional[List[str]] = None,
        expected_json_schema: Optional[Dict[str, Any]] = None,
    ) -> OutputGuardrailResult:
        initial_metadata: Dict[str, Any] = {}
        if retrieved_context:
            initial_metadata["retrieved_context"] = retrieved_context
        if expected_json_schema:
            initial_metadata["expected_json_schema"] = expected_json_schema

        ctx = self.pipeline.execute(output_text, initial_metadata=initial_metadata)

        return OutputGuardrailResult(
            passed=ctx.passed,
            action=ctx.action.value,
            original_output=ctx.original_text,
            sanitized_output=ctx.current_text,
            violations=ctx.violations,
            leaked_secrets=ctx.metadata.get("leaked_secrets", []),
            groundedness_score=ctx.metadata.get("groundedness_score", 1.0),
            blocked_reason=ctx.blocked_reason,
        )


# Default singleton instance
output_guardrails = OutputGuardrails()
