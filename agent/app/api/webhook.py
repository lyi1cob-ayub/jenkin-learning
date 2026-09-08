import os
import re
import asyncio
import httpx
import aiofiles
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional
from app.models.models import JenkinsWebhookPayload ,FeedbackRequest
from app.models.feedback import RCAFeedbackModel ,RCAAnalysisModel
from app.graph.state import AgentState
from app.graph.workflow import app as langgraph_app
from app.config import settings
from loguru import logger
from sqlalchemy.orm import Session
from app.db.db import get_db, init_db

router = APIRouter(prefix="/api/v1", tags=["Jenkins Webhook"])
# Add regex pattern to validate legitimate email formats
EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"

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

@router.api_route(
    "/feedback", methods=["GET", "POST"], status_code=status.HTTP_200_OK
)
async def submit_feedback(
    request: Request,
    payload: Optional[FeedbackRequest] = None,
    build_id: Optional[str] = Query(None),
    job_name: Optional[str] = Query(None),
    rating: Optional[str] = Query(None),
    predicted_failure_type: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    git_author_email: Optional[str] = Query(None),
    user_comments: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Ingests developer validation from POST (Teams Adaptive Cards) or GET (Email button clicks).

    Prevents duplicate submissions per user and renders HTML for browser clicks.
    """
    # 1. Parse JSON body if request is POST
    if request.method == "POST":
        try:
            body_data = await request.json()
            payload = FeedbackRequest(**body_data)
        except Exception as err:
            logger.warning(
                f"Failed to parse JSON payload for POST feedback: {err}"
            )

    # 2. Extract values with explicit preference (POST Body -> Query Parameters)
    b_id = (
        payload.build_id
        if payload and getattr(payload, "build_id", None)
        else build_id
    )
    j_name = (
        payload.job_name
        if payload and getattr(payload, "job_name", None)
        else job_name
    )
    r_type = (
        payload.rating
        if payload and getattr(payload, "rating", None)
        else rating
    )
    p_type = (
        payload.predicted_failure_type
        if payload and getattr(payload, "predicted_failure_type", None)
        else predicted_failure_type
    )
    u_comments = (
        payload.user_comments
        if payload and getattr(payload, "user_comments", None)
        else user_comments
    )

    # Resolve email with regex validation to reject bracket artifacts like '{'
    payload_email = (
        payload.user_email if payload and getattr(payload, "user_email", None) else None
    )
    raw_email = payload_email or user_email or git_author_email

    if raw_email and raw_email.strip() and re.match(EMAIL_REGEX, raw_email.strip()):
        u_email = raw_email.strip()
    else:
        u_email = "unknown_user@company.com"

    # Validate required parameters
    if not b_id or not j_name or not r_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required parameters: build_id, job_name, and rating are required.",
        )

    # 3. De-duplication Check: Has this specific user already submitted feedback?
    existing = (
        db.query(RCAFeedbackModel)
        .filter(
            RCAFeedbackModel.build_id == str(b_id),
            RCAFeedbackModel.job_name == str(j_name),
            RCAFeedbackModel.user_email == str(u_email),
        )
        .first()
    )

    if existing:
        msg = f"Feedback already recorded for build #{b_id} from {u_email}."
        if request.method == "GET":
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Feedback Already Recorded</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; background: #fdfce8; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                        .card {{ background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; max-width: 420px; border: 1px solid #fef08a; }}
                        .icon {{ font-size: 44px; color: #ca8a04; margin-bottom: 12px; }}
                        h2 {{ color: #854d0e; margin: 0 0 10px 0; }}
                        p {{ color: #713f12; font-size: 14px; line-height: 1.5; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <div class="icon">ℹ</div>
                        <h2>Feedback Already Submitted</h2>
                        <p>{msg}</p>
                    </div>
                </body>
                </html>
            """
            )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"status": "duplicate", "message": msg},
        )

    # 4. Fetch associated log snippet from agent execution state
    analysis = (
        db.query(RCAAnalysisModel)
        .filter(
            RCAAnalysisModel.build_id == str(b_id),
            RCAAnalysisModel.job_name == str(j_name),
        )
        .order_by(RCAAnalysisModel.created_at.desc())
        .first()
    )

    log_snippet = analysis.parsed_log_snippet if analysis else None
    actual_pred_type = p_type or (
        analysis.predicted_failure_type if analysis else "UNKNOWN"
    )

    # 5. Persist feedback record
    try:
        feedback_entry = RCAFeedbackModel(
            build_id=str(b_id),
            job_name=str(j_name),
            user_email=str(u_email),
            predicted_failure_type=str(actual_pred_type),
            rating=str(r_type).upper(),
            user_comments=u_comments
            or f"Submitted via {request.method} feedback link",
            raw_log_snippet=log_snippet,
        )
        db.add(feedback_entry)
        db.commit()
        db.refresh(feedback_entry)

        # 6. Return response (HTML for email clicks, JSON for API calls)
        if request.method == "GET":
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>RCA Feedback Confirmation</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; background: #f3f4f6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                        .card {{ background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; max-width: 420px; }}
                        .icon {{ font-size: 48px; color: #16a34a; margin-bottom: 12px; }}
                        h2 {{ color: #1f2937; margin: 0 0 10px 0; }}
                        p {{ color: #4b5563; font-size: 14px; line-height: 1.5; }}
                        .user-tag {{ font-weight: bold; color: #111827; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <div class="icon">✓</div>
                        <h2>Thank You!</h2>
                        <p>Your feedback for <strong>{j_name} #{b_id}</strong> has been recorded successfully for <span class="user-tag">{u_email}</span>.</p>
                    </div>
                </body>
                </html>
            """
            )

        return {
            "status": "success",
            "message": "Feedback recorded successfully",
            "record_id": feedback_entry.id,
            "user_email": u_email,
        }

    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to record feedback for build {b_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record feedback to database: {str(e)}",
        )