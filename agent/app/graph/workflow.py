from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.graph.nodes.log_parser_node import parse_log_node
from app.graph.nodes.rca_node import classify_rca_node
from app.graph.nodes.log_parser_node import parse_log_node
workflow = StateGraph(AgentState)

workflow.add_node("parse_log", parse_log_node)
workflow.add_node("classify_rca", classify_rca_node)

workflow.set_entry_point("parse_log")
workflow.add_edge("parse_log", "classify_rca")
workflow.add_edge("classify_rca", END)

app = workflow.compile()