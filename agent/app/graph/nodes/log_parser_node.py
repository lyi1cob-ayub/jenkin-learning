from typing import Dict, Any
from loguru import logger
from app.graph.state import AgentState
from app.tools.logparser import parse_jenkins_log_tool


def parse_log_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: Executes the log parser tool to extract structured error context.
    Updates state with formatted log snippets and high-priority error lines.
    """
    file_path = state.get("raw_log_path")

    if not file_path:
        logger.error("parse_log_node received an empty or missing 'raw_log_path' in state.")
        return {
            "sanitized_log_snippet": "Error: No raw log path provided in agent state.",
            "extracted_error_lines": []
        }

    try:
        # Execute tool via standard LangChain invocation interface
        parsed_results = parse_jenkins_log_tool.invoke({
            "file_path": file_path,
            "max_context_lines": 50
        })

        if not parsed_results:
            logger.warning(f"No log parse results returned for path: {file_path}")
            return {
                "sanitized_log_snippet": "No error context extracted from log file.",
                "extracted_error_lines": []
            }

        # Select top snippets (already sorted by priority in the tool)
        top_snippets = [item["context_snippet"] for item in parsed_results[:3]]
        matched_lines = [item["matched_line"] for item in parsed_results]

        return {
            "sanitized_log_snippet": "\n\n--- ERROR CONTEXT BOUNDARY ---\n\n".join(top_snippets),
            "extracted_error_lines": matched_lines
        }

    except Exception as e:
        logger.exception(f"Failed to parse Jenkins log at path '{file_path}': {str(e)}")
        return {
            "sanitized_log_snippet": f"Error encountered while parsing log: {str(e)}",
            "extracted_error_lines": []
        }