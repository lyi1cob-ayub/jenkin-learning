import os
import asyncio
import httpx
import aiofiles
from fastapi import APIRouter, HTTPException, status
from app.models.models import JenkinsWebhookPayload
from app.graph.state import AgentState
from app.graph.workflow import app as langgraph_app
from app.config import settings
from loguru import logger

router = APIRouter(prefix="/api/v1", tags=["Jenkins Webhook"])

# Absolute path resolution ensures consistency regardless of execution directory
LOG_STORAGE_DIR = os.path.abspath("./tmp/jenkins_raw_logs")
os.makedirs(LOG_STORAGE_DIR, exist_ok=True)

# Maintain strong references to running background tasks to prevent garbage collection
background_tasks_set = set()


async def run_agent_workflow(initial_state: AgentState):
    """Executes the LangGraph RCA pipeline asynchronously and logs state updates."""
    build_id = initial_state.get("build_id")
    try:
        logger.info(f"Starting LangGraph RCA workflow for build: {build_id}")
        final_state = await langgraph_app.ainvoke(initial_state)
        logger.info(f"LangGraph execution finished for build: {build_id}")
        logger.info(f"Final RCA Result: {final_state.get('rca_result')}")
    except Exception as e:
        logger.error(f"LangGraph execution failed for build {build_id}: {str(e)}")


@router.post("/analyse", status_code=status.HTTP_202_ACCEPTED)
async def receive_jenkins_webhook(payload: JenkinsWebhookPayload):
    """
    Receives Jenkins failure webhooks, streams logs directly to disk in O(1) RAM,
    and queues asynchronous LangGraph RCA processing.
    """
    logger.info(f"Received webhook for job '{payload.job_name}' build #{payload.build_id}")

    log_file_name = f"{payload.job_name}_build_{payload.build_id}.log"
    saved_log_path = os.path.join(LOG_STORAGE_DIR, log_file_name)

    auth = (settings.jenkins_user, settings.jenkins_token) if settings.jenkins_user and settings.jenkins_token else None

    try:
        # Chunked streaming prevents high memory usage on large log files
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream("GET", payload.log_url, auth=auth) as response:
                if response.status_code != status.HTTP_200_OK:
                    logger.error(f"Failed to fetch Jenkins log. HTTP {response.status_code}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to fetch Jenkins log. HTTP {response.status_code}"
                    )

                # Asynchronous file writing prevents blocking the event loop
                async with aiofiles.open(saved_log_path, "wb") as file:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        await file.write(chunk)

        logger.info(f"Successfully streamed raw log to disk: {saved_log_path}")

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

        # Queue background task safely with GC tracking
        task = asyncio.create_task(run_agent_workflow(initial_state))
        background_tasks_set.add(task)
        task.add_done_callback(background_tasks_set.discard)

        return {
            "status": "Accepted",
            "message": "Webhook received and agent execution queued",
            "raw_log_path": saved_log_path
        }

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Error handling webhook payload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook handling error: {str(e)}"
        )