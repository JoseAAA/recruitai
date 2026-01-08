"""
LLM Providers - Multi-provider abstraction for LLM integrations.
Supports: Ollama (local), OpenAI, Google Gemini
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Type, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""
    
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.base_url = settings.OLLAMA_HOST
        self.model = settings.OLLAMA_MODEL
        self._client = client
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client
    
    @property
    def name(self) -> str:
        return f"Ollama ({self.model})"
    
    async def is_available(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                return len(data.get("models", [])) > 0
            return False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        request_body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        if json_mode:
            request_body["format"] = "json"
        
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json=request_body
        )
        response.raise_for_status()
        return response.json().get("response", "")


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4, GPT-3.5, etc.)."""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.base_url = "https://api.openai.com/v1"
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    @property
    def name(self) -> str:
        return f"OpenAI ({self.model})"
    
    async def is_available(self) -> bool:
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            return False
        try:
            # Simple check - list models endpoint
            response = await self.client.get(f"{self.base_url}/models", timeout=10.0)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAI not available: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if json_mode:
            request_body["response_format"] = {"type": "json_object"}
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=request_body
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""
    
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client
    
    @property
    def name(self) -> str:
        return f"Gemini ({self.model})"
    
    async def is_available(self) -> bool:
        if not self.api_key:
            logger.warning("Gemini API key not configured")
            return False
        try:
            # Check by listing models
            response = await self.client.get(
                f"{self.base_url}/models?key={self.api_key}",
                timeout=10.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Gemini not available: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        # Gemini uses different endpoint structure
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        
        request_body = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        if json_mode:
            request_body["generationConfig"]["responseMimeType"] = "application/json"
        
        response = await self.client.post(url, json=request_body)
        response.raise_for_status()
        data = response.json()
        
        # Extract text from Gemini response structure
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return ""


def get_llm_provider() -> LLMProvider:
    """
    Factory function to get the configured LLM provider.
    Falls back to Ollama if configured provider is unavailable.
    """
    provider_name = settings.LLM_PROVIDER.lower()
    
    if provider_name == "openai":
        if settings.OPENAI_API_KEY:
            logger.info("Using OpenAI provider")
            return OpenAIProvider()
        else:
            logger.warning("OpenAI selected but no API key, falling back to Ollama")
    
    elif provider_name == "gemini":
        if settings.GEMINI_API_KEY:
            logger.info("Using Gemini provider")
            return GeminiProvider()
        else:
            logger.warning("Gemini selected but no API key, falling back to Ollama")
    
    # Default to Ollama
    logger.info("Using Ollama provider")
    return OllamaProvider()


# Singleton provider instance
_provider: Optional[LLMProvider] = None


def get_provider() -> LLMProvider:
    """Get cached provider instance."""
    global _provider
    if _provider is None:
        _provider = get_llm_provider()
    return _provider


async def reset_provider():
    """Reset provider (useful for testing or config changes)."""
    global _provider
    _provider = None
