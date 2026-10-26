import os
from pathlib import Path
from enum import Enum
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
import instructor
from openai import OpenAI

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

# 1. Define strict schema with constraints
class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class IncidentExtraction(BaseModel):
    service_name: str = Field(..., description="Target service affected")
    severity: SeverityLevel
    impacted_users_estimate: int = Field(..., ge=0)
    root_cause_summary: str = Field(..., max_length=200)

    # Semantic validation invariant
    @field_validator("impacted_users_estimate")
    @classmethod
    def validate_user_bounds(cls, v: int) -> int:
        if v > 10_000:
            raise ValueError("Estimate exceeds total active system users (10M)")
        return v

# 2. Patch client for automatic parsing and bounded retry injection
# Supports direct OpenAI or LiteLLM Proxy / AI Gateway if configured in .env
base_url = os.getenv("LITELLM_PROXY_URL") or os.getenv("AI_GATEWAY_URL") or None
api_key = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")

openai_client = OpenAI(
    base_url=base_url,
    api_key=api_key,
)
client = instructor.from_openai(openai_client)

def process_incident_report(raw_report: str) -> Optional[IncidentExtraction]:
    try:
        validated_record: IncidentExtraction = client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=IncidentExtraction,
            max_retries=2,  # Automatically re-prompts with validation error diffs
            messages=[
                {"role": "system", "content": "Extract incident data exactly as structured."},
                {"role": "user", "content": raw_report}
            ],
        )
        return validated_record
    except Exception as exc:
        # 3. Fallback routing when retries are exhausted
        log_to_dlq(raw_report=raw_report, error=str(exc))
        return None

def log_to_dlq(raw_report: str, error: str) -> None:
    # Ship to DLQ (Kafka/SQS) for inspection
    print(f"[DLQ Alert] Routing failed extraction to dead-letter queue: {error}")


if __name__ == "__main__":
    sample_report = (
        "CRITICAL ALERT: At 14:20 UTC, the payments-service experienced cascading connection pool "
        "exhaustion after a high spike in traffic. Roughly 25,000 active checkout sessions failed "
        "during a 15-minute window before the database read-replica auto-recovered."
    )
    print("=" * 60)
    print("Instructor Incident Extraction Demo (allrounder/functional)")
    print("=" * 60)
    print(f"[Endpoint]: {base_url or 'https://api.openai.com/v1 (Direct OpenAI)'}")
    print(f"[Gateway Mode]: {'LiteLLM Proxy' if base_url else 'Direct OpenAI'}\n")
    print(f"[Raw Incident Report]:\n{sample_report}\n")
    
    extracted = process_incident_report(sample_report)
    print("[Extracted Incident Record]:")
    print(extracted)
    print("=" * 60)
