import os
import re
import json
import time
import requests
import yaml
from pathlib import Path
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.models.models import RCAOutput


class OllamaRCAClient:
    """Client for interacting with local Ollama or OpenRouter via HTTP requests with automated fallback."""

    def __init__(self):
        self.base_url = settings.ollama_host.rstrip("/")
        self.registry = self._load_prompt_registry(settings.prompt_file_path)
        self.prompt_config = self._get_active_prompt_config()

        self.use_openrouter = (
            settings.use_openrouter 
            or os.getenv("USE_OPENROUTER", "false").lower() == "true"
        )
        self.openrouter_api_key = settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

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
                f"Prompt version '{version}' not found in registry. Available: {list(prompts_dict.keys())}"
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

        if self.use_openrouter:
            return self._call_openrouter(messages)
        return self._call_ollama(messages)

    @retry(
        wait=wait_exponential(min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((requests.exceptions.HTTPError, requests.exceptions.Timeout)),
        reraise=True
    )
    def _execute_openrouter_post(self, headers: dict, payload: dict) -> requests.Response:
        """Executes OpenRouter request with automatic retries on HTTP errors (429/5xx) and timeouts."""
        response = requests.post(self.openrouter_url, headers=headers, json=payload, timeout=60)
        
        # Trigger tenacity retry on HTTP 429 (Rate Limit) or 5xx Server Errors
        if response.status_code == 429 or response.status_code >= 500:
            logger.warning(f"OpenRouter returned status {response.status_code}. Retrying...")
            response.raise_for_status()
            
        return response

    def _call_openrouter(self, messages: list) -> dict:
        api_key = self.openrouter_api_key or settings.openrouter_api_key
        model = settings.openrouter_model

        if not api_key:
            logger.error("OpenRouter execution halted: API Key missing.")
            return self._call_ollama(messages)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.ollama_temperature,
            "response_format": {"type": "json_object"}
        }

        logger.info(f"Sending RCA request via OpenRouter to model [{model}]")

        try:
            response = self._execute_openrouter_post(headers, payload)
            response.raise_for_status()
            result_json = response.json()
            content_str = result_json["choices"][0]["message"]["content"].strip()
            return self._parse_and_validate(content_str)
            
        except Exception as e:
            logger.error(f"OpenRouter request failed after retries: {str(e)}. Falling back to local Ollama.")
            # Fallback path to local instance prevents pipeline termination
            return self._call_ollama(messages)

    def _call_ollama(self, messages: list) -> dict:
        chat_url = f"{self.base_url}/api/chat"
        model = settings.ollama_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": settings.ollama_temperature,
                "num_ctx": 2048,      # Reduced from 8192 to 2048 to speed up CPU inference
                "num_predict": 384     # Limit output length to prevent infinite token generation
            }
        }

        logger.info(f"Sending RCA request using prompt [{settings.active_prompt_version}] to Ollama [{model}]")

        try:
            response = requests.post(chat_url, json=payload, timeout=(5.0, 60.0))
            response.raise_for_status()
            result_json = response.json()
            content_str = result_json.get("message", {}).get("content", "{}").strip()
            return self._parse_and_validate(content_str)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to communicate with Ollama server via HTTP: {str(e)}")
            return self._build_fallback_schema(
                f"Ollama execution error: {str(e)}", 
                raw_evidence=str(e)
            )

    def _parse_and_validate(self, content_str: str) -> dict:
        """Safely cleans, extracts, and validates raw LLM output strings into RCAOutput dictionary format."""
        try:
            # Extract JSON payload enclosed within braces or markdown blocks
            json_match = re.search(r"\{.*\}", content_str, re.DOTALL)
            cleaned_content = json_match.group(0) if json_match else content_str.strip()
            
            parsed_dict = json.loads(cleaned_content)
            validated_rca = RCAOutput(**parsed_dict)
            return validated_rca.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse or validate LLM response into schema: {e}")
            return self._build_fallback_schema(
                "Failed to parse model response into structured format.",
                raw_evidence=content_str
            )

    def _build_fallback_schema(self, root_cause: str, raw_evidence: str) -> dict:
        """Helper to ensure a valid dictionary structure is always returned."""
        return {
            "domain": "Unknown",
            "root_cause": root_cause,
            "evidence": raw_evidence,
            "affected_component": "Unknown",
            "recommended_fix": "Review raw logs manually or verify API provider configuration.",
            "confidence": 0.0
        }