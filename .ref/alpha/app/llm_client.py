import requests
from loguru import logger
import yaml
from pathlib import Path
from app.config import settings
import json
from app.models import RCADiagnosisResponse

class OllamaRCAClient:
    """
    Client for interacting with local Ollama instance via raw HTTP requests 
    inside GitHub Codespaces.
    """

    def __init__(self):
        # Ensure base URL is clean (e.g. http://localhost:11434)
        self.base_url = settings.Ollama_host.rstrip("/")
        self.registry = self._load_prompt_registry(settings.prompt_file_path)
        self.prompt_config = self._get_active_prompt_config()

    def _load_prompt_registry(self, filepath: str) -> dict:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Prompt registry not found at {filepath}")
        
        with open(path, "r", encoding="utf-8") as file:
            registry = yaml.safe_load(file)
            logger.info(f"Loaded prompt registry from: {filepath}")
            return registry
        
    def _get_active_prompt_config(self) -> dict:
        prompts_dict = self.registry.get("prompts", {})
        version = settings.active_prompt_version
        
        if version not in prompts_dict:
            raise ValueError(f"Prompt version '{version}' not found in registry. Available: {list(prompts_dict.keys())}")
        
        logger.info(f"Successfully activated prompt version: {version}")
        return prompts_dict[version]

    def analyze_failure(self, error_snippet: str, file_context: str = "Not provided") -> dict:
        system_prompt = self.prompt_config.get("system_prompt", "")
        user_template = self.prompt_config.get("user_prompt_template", "")

        user_prompt = user_template.format(
            error_snippet=error_snippet,
            file_context=file_context
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        chat_url = f"{self.base_url}/api/chat"
        payload = {
            "model": settings.model_name,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_ctx": 8192
            }
        }

        logger.info(f"Sending RCA request using prompt version [{settings.active_prompt_version}] to model [{settings.model_name}] at {chat_url}")
        
        try:
            response = requests.post(chat_url, json=payload, timeout=300)
            response.raise_for_status()
            
            result_json = response.json()
            content_str = (
            result_json.get("message", {}).get("content", "{}").strip())

            # Clean up potential markdown code block wrappers if the model includes them
            cleaned_content = (
                content_str.replace("```json", "").replace("```", "").strip()
            )

            # Parse JSON and validate it against the Pydantic schema
            parsed_dict = json.loads(cleaned_content)
            validated_rca = RCADiagnosisResponse(**parsed_dict)
            return validated_rca.model_dump()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to communicate with Ollama server via HTTP: {str(e)}")
            raise RuntimeError(f"Ollama HTTP inference error: {str(e)}")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse or validate LLM response into schema: {e}")
            return {
                "root_cause_summary": (
                    "Failed to parse model response into structured format."
                ),
                "affected_file": "Unknown",
                "line_number": 0,
                "error_category": "Parsing Error",
                "raw_content": content_str if "content_str" in locals() else "",
            }