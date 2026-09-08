import asyncio
from app.graph.state import AgentState
from app.llm.client import OllamaRCAClient
from loguru import logger

from app.db.db import SessionLocal
from app.models.feedback import RCAAnalysisModel

# Reuse a single client instance to prevent reloading settings on every execution
rca_client = OllamaRCAClient()

def _persist_analysis_state(state: AgentState, rca_result):
    """Internal helper to save analysis execution state to DB."""
    db = SessionLocal()
    try:
        # 1. Safely extract domain string across dicts, objects, Pydantic models, and Enums
        if isinstance(rca_result, dict):
            domain_val = rca_result.get("domain", "")
        else:
            domain_val = getattr(rca_result, "domain", "")

        if hasattr(domain_val, "name"):
            domain_raw = str(domain_val.name).upper()
        elif hasattr(domain_val, "value"):
            domain_raw = str(domain_val.value).upper()
        else:
            domain_raw = str(domain_val).upper()

        predicted_type = "INFRASTRUCTURE" if "INFRA" in domain_raw else "APPLICATION_CODE"

        # 2. Extract log snippet safely and normalize lists to strings
        raw_snippet = state.get("sanitized_log_snippet")
        if not raw_snippet:
            error_lines = state.get("extracted_error_lines") or []
            snippet = "\n".join(error_lines) if isinstance(error_lines, list) else str(error_lines)
        elif isinstance(raw_snippet, list):
            snippet = "\n".join(raw_snippet)
        else:
            snippet = str(raw_snippet)

        # 3. Create database record
        analysis_record = RCAAnalysisModel(
            build_id=str(state.get("build_id")),
            job_name=str(state.get("job_name")),
            predicted_failure_type=predicted_type,
            parsed_log_snippet=snippet
        )
        db.add(analysis_record)
        db.commit()
        logger.info(f"Persisted analysis state for build #{state.get('build_id')} as {predicted_type}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to persist analysis state for build #{state.get('build_id')}: {str(e)}")
    finally:
        db.close()

async def classify_rca_node(state: AgentState) -> dict:
    """LangGraph Node: Takes sanitized log from state and runs Ollama RCA client asynchronously."""
    snippet = state.get("sanitized_log_snippet", "")
    
    if not snippet:
        logger.error("No log snippet found in state for RCA classification.")
        return {
            "error_message": "Log snippet missing.",
            "dispatch_status": "FAILED"
        }

    logger.info("Offloading RCA analysis to worker thread...")
    
    # Run the blocking synchronous HTTP call in a non-blocking thread pool
    rca_result = await asyncio.to_thread(
        rca_client.analyze_failure,
        error_snippet=snippet
    )
    if rca_result:
        _persist_analysis_state(state, rca_result)

    return {
        "rca_result": rca_result,
        "dispatch_status": "ANALYZED"
    }