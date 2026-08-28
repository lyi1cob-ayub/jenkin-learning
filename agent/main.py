import os 
from dotenv import load_dotenv
from enum import Enum
import json
import random
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from langgraph.graph import StateGraph, START,END
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool 
from IPython.display import Image, display

def display_graph(graph):
    return display(Image(graph.get_graph().draw_mermaid_png()))



llm = ChatOllama(model="qwen2.5-coder:7b",temperature=0.2)

response = llm.invoke("Hello, are you ready to analyze jenkins")
print(response.content)

class ErrorDomain(str, Enum):
    INFRASTUCTURE = "Infrastructure"
    APPLICATION_CODE = "Application Code"
    UNKNOWN = "Unknown"

class RCAOutput(BaseModel):
    """Structured response required from the LLM Node."""
    domain: ErrorDomain = Field(description="Classification of the error origin")
    root_cause: str = Field(description="Summary of why the build failed")
    evidence: str = Field(description="Exact line or snippet proving the root cause ")
    affected_componet: str = Field(description="Failed tool path, binary, or code file name")
    recommended_fix: str = Field(description="Actionable steps to resolve the failure ")
    confidence: float = Field(description="LLM confidence score between 0.0 and 1.0")

