from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory pointing to the 'app' directory (/agent/app)
APP_DIR = Path(__file__).resolve().parent
ENV_FILE_PATH = APP_DIR.parent / ".env"

class Settings(BaseSettings):
    app_name: str = "Bosch AI RCA agent"
    
    # Local Ollama Settings
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:1.5b"
    ollama_temperature: float = 0.2
    
    # OpenRouter Settings
    use_openrouter: bool = False
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen-2.5-coder-32b-instruct"
    
    # General Agent Settings
    prompt_file_path: str = str(APP_DIR / "prompts" / "prompts.yaml")
    max_log_lines: int = 100
    active_prompt_version: str = "v3"
    
    # Jenkins Integration
    jenkins_token: str = ""
    jenkins_user: str = ""
    teams_webhook_url: str = ""
    LOG_PARSER_MAX_CONTEXT_LINES: int = 40
    LOG_PARSER_MAX_TOTAL_CHARS: int = 24000
    LOG_PARSER_MAX_LINE_LENGTH: int = 2000

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

settings = Settings()