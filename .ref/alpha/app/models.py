from pydantic import BaseModel, Field


class RCADiagnosisResponse(BaseModel):
  root_cause_summary: str = Field(
      ..., description="Concise technical explanation of why the build failed."
  )
  affected_file: str = Field(
      ..., description="Exact file path identified from the logs or context"
  )
  line_number: int = Field(
      ..., description="Line number where the error occurred"
  )
  error_category: str = Field(
      ..., description="Classification of the error type"
  )