"""
client.py
Multi-provider AI LLM Client for the MSU SEO Intelligence Console.
Supports Google Gemini, OpenAI, Groq, Ollama / Local Models, and Offline Fallback.
Zero external SDK bloat; utilizes standard Python requests with full timeout protection.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Optional, Any
import requests
from dotenv import load_dotenv

from src.utils.logging import get_logger

logger = get_logger("ai_client")

# Ensure environment variables are loaded
env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

# Standard Provider Endpoints and Default Models
PROVIDERS_CONFIG = {
    "gemini": {
        "name": "Google Gemini",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "default_model": "gemini-2.5-flash",
        "models": ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        "env_keys": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    },
    "openai": {
        "name": "OpenAI",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        "env_keys": ["OPENAI_API_KEY"],
    },
    "groq": {
        "name": "Groq (Fast Llama)",
        "api_url": "https://api.groq.com/openai/v1/chat/completions",
        "default_model": "llama-3.3-70b-versatile",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "env_keys": ["GROQ_API_KEY"],
    },
    "ollama": {
        "name": "Ollama / Local LLM",
        "api_url": "http://localhost:11434/v1/chat/completions",
        "default_model": "llama3.2",
        "models": ["llama3.2", "llama3", "mistral", "qwen2.5", "deepseek-r1:8b"],
        "env_keys": [],
    },
    "local": {
        "name": "Local Data Analyst (Zero API Key / Offline)",
        "api_url": None,
        "default_model": "rule-sql-engine",
        "models": ["rule-sql-engine"],
        "env_keys": [],
    }
}


class AIClient:
    """Unified interface to call various AI providers."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = (provider or os.getenv("AI_PROVIDER", "gemini")).lower().strip()
        if self.provider not in PROVIDERS_CONFIG:
            self.provider = "gemini"

        cfg = PROVIDERS_CONFIG[self.provider]
        self.api_key = api_key or self._resolve_env_key(cfg["env_keys"])
        self.model = model or os.getenv("AI_MODEL", cfg["default_model"])
        self.base_url = base_url or os.getenv("AI_BASE_URL", cfg["api_url"])

    def _resolve_env_key(self, env_keys: List[str]) -> Optional[str]:
        for k in env_keys:
            val = os.getenv(k)
            if val and val.strip():
                return val.strip()
        return None

    def has_valid_credentials(self) -> bool:
        if self.provider in ("local", "ollama"):
            return True
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> str:
        """
        Sends messages to the configured LLM provider and returns text response.
        Raises RuntimeError on API failure with helpful message.
        """
        if self.provider == "local":
            raise NotImplementedError("Local provider should be handled by the local engine.")

        if not self.has_valid_credentials():
            raise ValueError(
                f"Missing API key for provider '{self.provider}'. "
                f"Please configure it in .env ({', '.join(PROVIDERS_CONFIG[self.provider]['env_keys'])}) "
                f"or enter it in the AI Chatbot sidebar settings."
            )

        # Build payload adhering to standard chat completions schema
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=30,
            )
            
            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "").strip()
                return "Received empty response from AI model."
            
            error_detail = response.text
            try:
                err_json = response.json()
                if "error" in err_json:
                    error_detail = err_json["error"].get("message", error_detail)
            except Exception:
                pass

            if response.status_code == 401 or response.status_code == 403:
                raise RuntimeError(
                    f"Authentication error with {self.provider.capitalize()} API (Status {response.status_code}): {error_detail}. "
                    "Please verify your API key."
                )
            elif response.status_code == 429:
                raise RuntimeError(
                    f"Rate limit exceeded on {self.provider.capitalize()} API. Please try again in a few moments."
                )
            else:
                raise RuntimeError(
                    f"{self.provider.capitalize()} API returned HTTP {response.status_code}: {error_detail}"
                )

        except requests.exceptions.Timeout:
            raise RuntimeError(f"Request to {self.provider.capitalize()} timed out after 30 seconds.")
        except requests.exceptions.ConnectionError as ce:
            raise RuntimeError(f"Failed to connect to {self.provider.capitalize()} at {self.base_url}: {ce}")
        except Exception as e:
            if isinstance(e, (RuntimeError, ValueError)):
                raise
            raise RuntimeError(f"Unexpected error communicating with {self.provider.capitalize()}: {e}")

