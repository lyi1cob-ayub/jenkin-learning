from app.graph.state import AgentState
from app.tools.logparser import parse_jenkins_log_tool


def parse_log_node(state: AgentState)-> dict:
    """Node 1: Executes the log parser tool to extract key error context."""

    file_path = state["raw_log_path"]

    parsed_results = parse_jenkins_log_tool.invoke({"file_path": file_path, "max_context_lines":50})

    top_snippets = [item["context_snippet"] for item in parsed_results[:3]]
    matched_lines = [item["matched_line"] for item in parsed_results]

    return{
        "sanitized_log_snippet": "\n---\n".join(top_snippets),
        "extracted_error_lines": matched_lines
    }

