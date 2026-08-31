from app.graph.state import AgentState
from app.llm.client import OllamaRCAClient
from loguru import logger

def classify_rca_node(state: AgentState) -> dict:
    """LangGraph Node: Takes sanitized log from state and runs Ollama RCA client."""
    snippet = state.get("sanitized_log_snippet", "")
    
    if not snippet:
        logger.error("No log snippet found in state for RCA classification.")
        return {
            "error_message": "Log snippet missing.",
            "dispatch_status": "FAILED"
        }

    client = OllamaRCAClient()
    rca_result = client.analyze_failure(error_snippet=snippet)

    return {
        "rca_result": rca_result,
        "dispatch_status": "ANALYZED"
    }