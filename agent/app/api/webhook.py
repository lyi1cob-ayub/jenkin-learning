import os
import requests
from fastapi import APIRouter, BackgroundTasks , HTTPException
from app.models.models import JenkinsWebhookPayload
from app.graph.state import AgentState
from app.graph.workflow import app as langgraph_app
router = APIRouter(prefix="/api/v1", tags=["Jenkins Webhook"])

Log_Storage_Dir = "../tmp/Jenkins_raw_logs"
os.makedirs(Log_Storage_Dir, exist_ok=True)

@router.post("/analyse")
async def receive_jenkins_webhook(payload: JenkinsWebhookPayload , background_tasks: BackgroundTasks):
    try:
        response = requests.get(payload.log_url, timeout=100)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch the log from the jenkins ")
        raw_log_text = response.text

        log_file_name = f"{payload.job_name}_build_{payload.build_id}.log"

        saved_log_path = os.path.join(Log_Storage_Dir, log_file_name)

        with open(saved_log_path, "w",encoding="utf-8") as file:
            file.write(raw_log_text)

        initial_state: AgentState = {
            "build_id": payload.build_id,
            "job_name": payload.job_name,
            "raw_log_path": saved_log_path,
            "git_author_email": payload.git_author_email,
            "gerrit_change_id": payload.gerrit_change_id,
            "sanitized_log_snippet": None,
            "extracted_error_lines": [],
            "rca_result": None,
            "assigned_owner_email": None,
            "drafted_notification_body": None,
            "is_approved": None,
            "dispatch_status": "PENDING",
            "error_message": None,
        }

        background_tasks.add_task(langgraph_app.invoke , initial_state)

        return{
            "status": "Accepted",
            "message": "Webhook received and agent execution queued",
            "raw_log_path": saved_log_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"webhook handling error :{str(e)}")