import os
import re
import json
import time
import requests
import yaml
import logging
from pathlib import Path
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger


from app.config import settings
from app.models.models import RCAOutput
from langfuse import Langfuse
try:
    from langfuse.decorators import observe, langfuse_context
except ImportError:
    from langfuse import observe
    try:
        from langfuse import langfuse_context
    except ImportError:
        langfuse_context = None

logging.basicConfig(level=logging.INFO)
logging.getLogger("langfuse").setLevel(logging.DEBUG)

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
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
            os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
            os.environ["LANGFUSE_HOST"] = settings.langfuse_host

            self.langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host
            )
            logger.info(f"Initialized Langfuse client pointing to {settings.langfuse_host}")
        else:
            self.langfuse = None
            logger.warning("Langfuse credentials not set. Tracing running in passive mode.")

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
    @observe(name="RCA_Analysis_Root")
    def analyze_failure(self, error_snippet: str, file_context: str = "Not provided") -> dict:
        try:
            # 1. Fetch the prompt tagged with "production" label from Langfuse
            langfuse_prompt = self.langfuse.get_prompt("v5_qwen3_14b", label="production")
            
            # 2. Compile variables (error_snippet and file_context) into prompt messages
            compiled_messages = langfuse_prompt.compile(
                error_snippet=error_snippet,
                file_context=file_context
            )
            
            # 3. Format messages for API calls (OpenRouter / Ollama)
            messages = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in compiled_messages
            ]
            
            # 4. Link prompt version to active trace observation for tracking
            if langfuse_context is not None:
                langfuse_context.update_current_observation(prompt=langfuse_prompt)
                
            logger.info(f"Loaded prompt version {langfuse_prompt.version} from Langfuse UI (label: production).")
            
        except Exception as e:
            logger.warning(f"Failed to fetch prompt from Langfuse UI: {e}. Falling back to local prompt.yml.")
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
    @observe(as_type="generation", name="OpenRouter_Generation")
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
            if langfuse_context is not None:
                langfuse_context.update_current_observation(
                    model=model,
                    input=messages,
                    output=content_str,
                    usage={
                        "input": result_json.get("usage", {}).get("prompt_tokens", 0),
                        "output": result_json.get("usage", {}).get("completion_tokens", 0),
                    },
                )
            return self._parse_and_validate(content_str)
            
        except Exception as e:
            logger.error(f"OpenRouter request failed after retries: {str(e)}. Falling back to local Ollama.")
            # Fallback path to local instance prevents pipeline termination
            return self._call_ollama(messages)
    @observe(as_type="generation", name="Ollama_Generation")
    def _call_ollama(self, messages: list) -> dict:
        chat_url = f"{self.base_url}/api/chat"
        model = settings.ollama_model
        num_ctx = self.prompt_config.get("num_ctx", 2048)
        num_predict = self.prompt_config.get("num_predict", 384)
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "think": True,
            "options": {
                "temperature": settings.ollama_temperature,
                "num_ctx": num_ctx,      # Reduced from 8192 to 2048 to speed up CPU inference
                "num_predict": num_predict     # Limit output length to prevent infinite token generation
            }
        }

        logger.info(f"Sending RCA request using prompt [{settings.active_prompt_version}] to Ollama [{model}]")

        try:
            with requests.Session() as session:
                session.trust_env = False
                response = requests.post(chat_url, json=payload, timeout=(10.0, 180.0))
                response.raise_for_status()
                result_json = response.json()
                content_str = result_json.get("message", {}).get("content", "{}").strip()
                if langfuse_context is not None:
                    langfuse_context.update_current_observation(
                        model=model,
                        input=messages,
                        output=content_str,
                        usage={
                            "input": result_json.get("prompt_eval_count", 0),
                            "output": result_json.get("eval_count", 0),
                        },
                    )
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
            think_match = re.search(r"<think>(.*?)</think>", content_str, re.DOTALL)
            if think_match:
                think_length = len(think_match.group(1).strip())
                logger.info(f"Model produced a thinking block ({think_length} chars): {think_match.group(1).strip()[:200]}...")
            else:
                logger.info("No <think> block found in model output.")
            content_str = re.sub(r"<think>.*?</think>", "", content_str, flags=re.DOTALL).strip()
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