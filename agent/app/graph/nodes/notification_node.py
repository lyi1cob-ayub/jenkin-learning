# app/graph/nodes/notification_node.py
import asyncio
from app.graph.state import AgentState
from app.tools.notifications import send_teams_rca_card
from loguru import logger

async def notify_teams_node(state: AgentState) -> dict:
    rca_result = state.get("rca_result")
    
    if not rca_result:
        logger.error("Skipping Teams notification: No rca_result found in state.")
        return {"dispatch_status": "FAILED"}

    # Convert Pydantic RCAOutput model to dict if necessary
    rca_dict = rca_result.model_dump() if hasattr(rca_result, "model_dump") else dict(rca_result)

    logger.info("Offloading Teams notification dispatch to thread...")
    success = await asyncio.to_thread(
        send_teams_rca_card,
        rca_result=rca_dict,
        job_name=state.get("job_name", ""),
        build_id=state.get("build_id", ""),
        author_email=state.get("git_author_email") or "",
        change_id=state.get("gerrit_change_id") or ""
    )

    return {
        "dispatch_status": "DISPATCHED" if success else "FAILED"
    }