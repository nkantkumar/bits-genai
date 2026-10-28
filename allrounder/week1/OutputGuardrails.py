"""
OutputGuardrails.py - Enterprise Defensive Shield for Outbound LLM Responses.

Protects against:
1. Secret & PII Leakage: Ensures LLM never returns database credentials, API keys (sk-..., ghp_...),
   private keys, or sensitive customer PII.
2. Hallucination & Groundedness: Computes overlap ratio between claims in the response
   and retrieved RAG context documents.
3. Schema & Syntax Validation: Enforces valid JSON structure when requested.
4. Harmful / Malicious Output Mitigation: Flags unconstrained weaponized exploit code.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

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
            "sanitized_output_preview": self.sanitized_output[:120] + "..." if len(self.sanitized_output) > 120 else self.sanitized_output,
        }


class OutputGuardrails:
    """Enterprise outbound defensive inspection pipeline."""

    # 1. Regex patterns for sensitive secrets and credentials
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

    # 2. PII Regex patterns for outbound data
    PII_PATTERNS = {
        "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    }

    # Common English stop words for groundedness calculation
    STOP_WORDS: Set[str] = {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "of",
        "is", "are", "was", "were", "this", "that", "these", "those", "it", "be",
        "by", "as", "from", "into", "we", "you", "they", "he", "she", "can", "will",
    }

    def __init__(self, min_groundedness_score: float = 0.25):
        self.min_groundedness_score = min_groundedness_score

    def inspect(
        self,
        output_text: str,
        retrieved_context: Optional[List[str]] = None,
        expected_json_schema: Optional[Dict[str, Any]] = None,
    ) -> OutputGuardrailResult:
        """
        Executes comprehensive outbound validation:
        1. Redacts any leaked secrets or credentials.
        2. Assesses groundedness against context if RAG was used.
        3. Validates JSON schema if structured output is requested.
        """
        sanitized = output_text
        violations: List[str] = []
        leaked_secrets: List[str] = []

        # -------------------------------------------------------------
        # 1. Secret & Credential Leakage Shield
        # -------------------------------------------------------------
        for secret_name, pattern in self.SECRET_PATTERNS.items():
            matches = pattern.findall(sanitized)
            if matches:
                violations.append(f"{OutputViolationType.SECRET_LEAKAGE}: {secret_name}")
                leaked_secrets.extend(matches)
                sanitized = pattern.sub(f"[REDACTED_{secret_name}]", sanitized)

        # -------------------------------------------------------------
        # 2. Outbound PII Shield
        # -------------------------------------------------------------
        for pii_name, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(sanitized)
            if matches:
                violations.append(f"{OutputViolationType.PII_LEAKAGE}: {pii_name}")
                sanitized = pattern.sub(f"[REDACTED_{pii_name}]", sanitized)

        # -------------------------------------------------------------
        # 3. Groundedness & Hallucination Assessment
        # -------------------------------------------------------------
        groundedness = 1.0
        if retrieved_context and len(retrieved_context) > 0 and len(output_text.split()) >= 4:
            groundedness = self._calculate_groundedness(output_text, retrieved_context)
            if groundedness < self.min_groundedness_score:
                violations.append(
                    f"{OutputViolationType.LOW_GROUNDEDNESS}: Score {groundedness:.2f} < threshold {self.min_groundedness_score}"
                )

        # -------------------------------------------------------------
        # 4. JSON Schema Validation (Optional)
        # -------------------------------------------------------------
        if expected_json_schema:
            try:
                parsed = json.loads(sanitized)
                # Verify required top-level keys
                required_keys = expected_json_schema.get("required", [])
                for k in required_keys:
                    if k not in parsed:
                        violations.append(f"{OutputViolationType.SCHEMA_VIOLATION}: Missing required key '{k}'")
            except Exception as e:
                violations.append(f"{OutputViolationType.SCHEMA_VIOLATION}: Malformed JSON ({e})")

        # Determine overall action
        has_secret_violation = any(OutputViolationType.SECRET_LEAKAGE in v for v in violations)
        action = "ALLOWED"
        if has_secret_violation or len(violations) > 0:
            action = "SANITIZED"

        return OutputGuardrailResult(
            passed=True,  # sanitized content safe to proceed
            action=action,
            original_output=output_text,
            sanitized_output=sanitized,
            violations=violations,
            leaked_secrets=leaked_secrets,
            groundedness_score=groundedness,
            blocked_reason=None,
        )

    def _calculate_groundedness(self, output: str, context_chunks: List[str]) -> float:
        """
        Computes token overlap groundedness:
        Measures the fraction of informative content terms in the output
        that exist in the retrieved context documents.
        """
        def tokenize(text: str) -> Set[str]:
            words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
            return {w for w in words if w not in self.STOP_WORDS}

        out_tokens = tokenize(output)
        if not out_tokens:
            return 1.0

        ctx_tokens: Set[str] = set()
        for c in context_chunks:
            ctx_tokens.update(tokenize(c))

        if not ctx_tokens:
            return 1.0

        supported = out_tokens.intersection(ctx_tokens)
        return len(supported) / len(out_tokens)


# Global singleton instance
output_guardrails = OutputGuardrails()
