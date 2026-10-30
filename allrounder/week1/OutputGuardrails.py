"""
OutputGuardrails.py - Backward Compatibility Shim.
All implementations have been reorganized into the `guardrails/` package following
the Chain of Responsibility and Filter / Interceptor Design Patterns.
"""

import sys
from pathlib import Path

WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from guardrails import (
    GroundednessFilter,
    JevGroundednessFilter,
    OutputGuardrailResult,
    OutputGuardrails,
    OutputViolationType,
    SchemaValidationFilter,
    SecretLeakageFilter,
    output_guardrails,
)

__all__ = [
    "GroundednessFilter",
    "JevGroundednessFilter",
    "OutputGuardrailResult",
    "OutputGuardrails",
    "OutputViolationType",
    "SchemaValidationFilter",
    "SecretLeakageFilter",
    "output_guardrails",
]

if __name__ == "__main__":
    test_outputs = [
        "The operation succeeded. Internal key is sk-abcdef1234567890abcdef12345678.",
        "PostgreSQL connection: postgresql://admin:supersecret@db.internal:5432/production",
        "Normal safe answer without secrets.",
    ]
    print("=" * 70)
    print(" Testing Outbound Guardrails (Filter / Interceptor Pattern)")
    print("=" * 70)
    for out in test_outputs:
        res = output_guardrails.inspect(out)
        print(f"\nRaw Output: \"{out}\"")
        print(f" -> Action:    {res.action}")
        print(f" -> Sanitized: \"{res.sanitized_output}\"")
        if res.violations:
            print(f" -> Violations: {res.violations}")
