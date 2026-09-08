from enum import Enum
from pydantic import BaseModel, Field ,field_validator
from typing import Optional


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


    @field_validator("domain",mode="before")
    @classmethod
    def normalize_domain(cls,value:str)->str:
        """Handles casing inconsistencies from local LLM outputs."""
        if isinstance(value,str):
            val_lower= value.strip().lower()
            if "infra" in val_lower:
                return ErrorDomain.INFRASTRUCTURE.value
            elif "code" in val_lower or "app" in val_lower:
                return ErrorDomain.APPLICATION_CODE.value
        return value

class JenkinsWebhookPayload(BaseModel):
    build_id: str = Field(description="Jenkins build number")
    job_name: str = Field(description="Jenkins job name")
    log_url: str = Field(description="URL of the console log of the build")
    git_author_email: Optional[str] = None 
    gerrit_change_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    build_id: str
    job_name: str
    rating: str  # "UP" or "DOWN"
    predicted_failure_type: Optional[str] = None
    corrected_failure_type: Optional[str] = None
    user_comments: Optional[str] = None
    raw_log_snippet: Optional[str] = None
    user_email: Optional[str] = None  # Add this line