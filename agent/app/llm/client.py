from langchain_ollama import ChatOllama
from app.config import (OLLAMA_MODEL,OLLAMA_TEMPERATURE)


def create_llm() ->ChatOllama:
    return ChatOllama(
        model=OLLAMA_MODEL,
        temperature=OLLAMA_TEMPERATURE,
        )