import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Bosch AI RCA agent"
    Ollama_host: str = os.getenv("OLLAMA_HOST","https://localhost:11434")
    model_name: str = os.getenv("MODEL_NAME","qwen2.5-coder:14b")
    prompt_version_file: str = "prompts/prompts.yaml"
    max_log_lines: int = 100

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()