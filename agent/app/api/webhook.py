import os
import asyncio
import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.models.models import JenkinsWebhookPayload
from app.graph.state import AgentState
from app.graph.workflow import app as langgraph_app
from app.config import settings
from loguru import logger

router = APIRouter(prefix="/api/v1", tags=["Jenkins Webhook"])

Log_Storage_Dir = "../tmp/Jenkins_raw_logs"
os.makedirs(Log_Storage_Dir, exist_ok=True)
JENKINS_USER = settings.jenkins_user
JENKINS_TOKEN = settings.jenkins_token

async def run_agent_workflow(initial_state: AgentState):
    """Wrapper function to execute LangGraph asynchronously and log errors."""
    try:
        logger.info(f"Starting LangGraph workflow for build {initial_state['build_id']}...")
        final_state = await langgraph_app.ainvoke(initial_state)
        logger.info(f"LangGraph execution finished for build {initial_state['build_id']}.")
        logger.info(f"Final RCA Result: {final_state.get('rca_result')}")
    except Exception as e:
        logger.error(f"LangGraph execution failed for build {initial_state['build_id']}: {str(e)}")

@router.post("/analyse")
async def receive_jenkins_webhook(payload: JenkinsWebhookPayload, background_tasks: BackgroundTasks):
    print(f"--> Received log_url: {payload.log_url}")
    print(f"--> Authenticating with user: {JENKINS_USER}")
    
    try:
        auth = (JENKINS_USER, JENKINS_TOKEN) if JENKINS_USER and JENKINS_TOKEN else None
        
        # Async HTTP client prevents Uvicorn event loop freezing
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(payload.log_url, auth=auth)
            
        print(f"--> Jenkins Response Code: {response.status_code}")
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to fetch log. Status: {response.status_code}, Body: {response.text[:200]}"
            )

        raw_log_text = response.text
        log_file_name = f"{payload.job_name}_build_{payload.build_id}.log"
        saved_log_path = os.path.join(Log_Storage_Dir, log_file_name)

        with open(saved_log_path, "w", encoding="utf-8") as file:
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

        # Queue async task safely without blocking background workers
        asyncio.create_task(run_agent_workflow(initial_state))

        return {
            "status": "Accepted",
            "message": "Webhook received and agent execution queued",
            "raw_log_path": saved_log_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"webhook handling error: {str(e)}")