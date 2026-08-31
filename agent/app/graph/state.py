from typing import Optional , TypedDict
from app.models.models import RCAOutput

class AgentState(TypedDict):
    build_id: str
    job_name: str
    raw_log_path: str
    git_author_email: Optional[str]
    gerrit_change_id: Optional[str]

    #for the log parser output
    sanitized_log_snippet: Optional[str]
    extracted_error_lines: Optional[str]
    #llm output
    rca_result: Optional[RCAOutput]

    assigned_owner_email: Optional[str]
    drafted_notification_body: Optional[str]

    is_approved: Optional[bool]
    dispatch_status: str
    error_message: Optional[str]
