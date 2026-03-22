"""
LLM Providers - Multi-provider abstraction for LLM integrations.
Supports: Ollama (local), OpenAI, Google Gemini
"""
import json
import logging
import re
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
        max_tokens: int = 2000,
        system_prompt: str = None,
    ) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        pass
    
    async def close(self):
        """Close any open connections. Override in subclasses."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider — Edge AI, 100% privado."""
    
    def __init__(self, client: Optional[httpx.AsyncClient] = None, model: Optional[str] = None):
        self.base_url = settings.OLLAMA_HOST
        self.model = model or settings.MATCH_MODEL
        self._client = client
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client
    
    async def close(self):
        """Close HTTP client to free connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    @property
    def name(self) -> str:
        return f"Ollama ({self.model})"
    
    async def is_available(self) -> bool:
        """Check if Ollama is running AND has the configured model installed."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                # Check if the CONFIGURED model is installed
                for name in model_names:
                    if self.model in name:
                        return True
                
                # Model not found — tell user which models exist
                logger.warning(
                    f"Ollama running but model '{self.model}' not found. "
                    f"Available: {model_names}. Run: ollama pull {self.model}"
                )
                return False
            return False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        system_prompt: str = None,
    ) -> str:
        """
        Generate text using Ollama /api/chat endpoint.
        
        Uses /api/chat instead of /api/generate because:
        - Supports system role → better instruction following
        - Standard message format compatible with all models
        - Better structured output for Qwen 3.5
        """
        messages = []
        
        # System prompt — gives the model its role/instructions
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # User message — the actual prompt
        messages.append({"role": "user", "content": prompt})
        
        # Auto-detect /no_think token: translates prompt hint to Ollama API param.
        # This is critical for qwen3.5 — without "think": false the model spends
        # all num_predict tokens on chain-of-thought and emits empty content.
        has_no_think = any(
            msg.get("content", "").lstrip().startswith("/no_think")
            for msg in messages
            if msg.get("role") == "user"
        )
        if has_no_think:
            # Strip the /no_think prefix from the user message (already handled by API param)
            for msg in messages:
                if msg.get("role") == "user":
                    msg["content"] = re.sub(r"^/no_think\s*\n?", "", msg["content"].lstrip(), count=1)

        request_body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        if has_no_think:
            request_body["think"] = False
        if json_mode:
            request_body["format"] = "json"
        
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=request_body
        )
        response.raise_for_status()
        data = response.json()

        # /api/chat returns {"message": {"role": "assistant", "content": "...", "thinking": "..."}}
        # qwen3.5 uses a separate "thinking" field for chain-of-thought reasoning.
        # When thinking is enabled and the final answer is also JSON, both fields are populated.
        # We prefer "content" (the actual answer), but fall back to "thinking" only as a last resort.
        message = data.get("message", {})
        content = message.get("content", "")
        thinking = message.get("thinking", "")

        # If content is empty but thinking has data, the model put its response in thinking.
        # This happens when json_mode+thinking fills tokens before generating a separate content.
        # In that case extract any JSON from the thinking block.
        if not content.strip() and thinking.strip():
            logger.debug(f"Ollama: content empty, using thinking field ({len(thinking)} chars)")
            return thinking

        return content


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
    
    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
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
        max_tokens: int = 2000,
        system_prompt: str = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        request_body = {
            "model": self.model,
            "messages": messages,
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
    
    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
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
        max_tokens: int = 2000,
        max_retries: int = 3,
        system_prompt: str = None,
    ) -> str:
        """
        Generate text with automatic retry on rate limit (429) errors.
        Uses exponential backoff: 1s, 2s, 4s delays between retries.
        """
        import asyncio
        
        # Gemini uses different endpoint structure
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        
        # Gemini REST API: system instructions go as a separate field
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        
        request_body = {
            "contents": [
                {"parts": [{"text": full_prompt}]}
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        if json_mode:
            request_body["generationConfig"]["responseMimeType"] = "application/json"
        
        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self.client.post(url, json=request_body)
                
                # Handle rate limiting with retry
                if response.status_code == 429:
                    wait_time = 2 ** attempt  # 1, 2, 4 seconds
                    logger.warning(
                        f"Gemini rate limit (429), retry {attempt + 1}/{max_retries} "
                        f"in {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                # Extract text from Gemini response structure
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError) as e:
                    logger.error(f"Failed to parse Gemini response: {e}")
                    return ""
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"Gemini rate limit, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                last_error = e
                logger.error(f"Gemini generate error: {e}")
                raise
        
        # All retries exhausted
        logger.error(f"Gemini max retries exceeded. Last error: {last_error}")
        raise Exception(f"Gemini API rate limit exceeded after {max_retries} retries")


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
