import json
from pathlib import Path
import requests
import yaml
from loguru import logger

from app.config import settings
from app.models.models import RCAOutput

class OllamaRCAClient:
    """Client for interacting with local Ollama instance via HTTP requests."""

    def __init__(self):
        # Access attributes safely from app.config settings
        self.base_url = settings.ollama_host.rstrip("/")
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
            raise ValueError(
                f"Prompt version '{version}' not found in registry. "
                f"Available: {list(prompts_dict.keys())}"
            )
        
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
                "temperature": settings.temperature if hasattr(settings, "temperature") else 0.1,
                "num_ctx": 8192
            }
        }

        logger.info(f"Sending RCA request using prompt [{settings.active_prompt_version}] to model [{settings.model_name}]")
        
        try:
            response = requests.post(chat_url, json=payload, timeout=300)
            response.raise_for_status()
            
            result_json = response.json()
            content_str = result_json.get("message", {}).get("content", "{}").strip()

            cleaned_content = (
                content_str.replace("```json", "").replace("```", "").strip()
            )

            # Validate against RCAOutput model matching models.py
            parsed_dict = json.loads(cleaned_content)
            validated_rca = RCAOutput(**parsed_dict)
            return validated_rca.model_dump()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to communicate with Ollama server via HTTP: {str(e)}")
            raise RuntimeError(f"Ollama HTTP inference error: {str(e)}")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse or validate LLM response into schema: {e}")
            return {
                "domain": "Unknown",
                "root_cause": "Failed to parse model response into structured format.",
                "evidence": content_str if "content_str" in locals() else "",
                "affected_component": "Unknown",
                "recommended_fix": "Review raw logs manually or check prompt formatting.",
                "confidence": 0.0
            }
