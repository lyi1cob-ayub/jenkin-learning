import asyncio
from app.graph.state import AgentState
from app.llm.client import OllamaRCAClient
from loguru import logger

# Reuse a single client instance to prevent reloading settings on every execution
rca_client = OllamaRCAClient()

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

    return {
        "rca_result": rca_result,
        "dispatch_status": "ANALYZED"
    }