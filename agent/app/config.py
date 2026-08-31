# app/config.py
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    app_name: str = "Bosch AI RCA agent"
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model_name: str = os.getenv("MODEL_NAME", "qwen2.5-coder:7b")
    temperature: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
    prompt_file_path: str = "prompts/prompts.yaml"
    max_log_lines: int = 100
    active_prompt_version: str = "v3"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
