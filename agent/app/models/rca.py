from enum import Enum
from pydantic import BaseModel, Field ,field_validator

class ErrorDomain(str, Enum):
    INFRASTRUCTURE = "Infrastructure"
    APPLICATION_CODE = "Application Code"
    UNKNOWN = "Unknown"

class RCAOutput(BaseModel):
    """Structured response required from the LLM Node."""
    domain: ErrorDomain = Field(description="Classification of the error origin")
    root_cause: str = Field(description="Summary of why the build failed")
    evidence: str = Field(description="Exact line or snippet proving the root cause ")
    affected_component: str = Field(description="Failed tool path, binary, or code file name")
    recommended_fix: str = Field(description="Actionable steps to resolve the failure ")
    confidence: float = Field(ge=0.0,le=1.0,description="LLM confidence score between 0.0 and 1.0")


    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

        return value