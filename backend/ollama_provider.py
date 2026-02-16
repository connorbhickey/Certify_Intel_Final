"""
Certify Intel - Ollama Local LLM Provider
==========================================
Run Llama 3.1, Mistral, Qwen locally for $0 API costs.
OpenAI-compatible REST API on port 11434.

Config:
    OLLAMA_ENABLED=false (default OFF)
    OLLAMA_URL=http://localhost:11434
    OLLAMA_DEFAULT_MODEL=llama3.1:8b
"""

import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.1:8b")


class OllamaProvider:
    """Local LLM provider via Ollama."""

    def __init__(self):
        self._client = None
        self.is_available = OLLAMA_ENABLED
        self.default_model = OLLAMA_DEFAULT_MODEL

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key="ollama",  # Ollama doesn't need a real key
                    base_url=f"{OLLAMA_URL}/v1"
                )
            except ImportError:
                logger.warning("openai package required for Ollama provider")
                self.is_available = False
        return self._client

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate via local Ollama."""
        client = self._get_client()
        if not client:
            raise RuntimeError("Ollama client not available")

        use_model = model or self.default_model
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=use_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        text = response.choices[0].message.content or ""
        tokens = (
            response.usage.completion_tokens
            if response.usage
            else len(text.split())
        )
        input_tokens = (
            response.usage.prompt_tokens
            if response.usage
            else len(prompt.split())
        )

        return {
            "response": text,
            "tokens_input": input_tokens,
            "tokens_output": tokens,
            "model": use_model,
        }

    async def list_models(self) -> List[str]:
        """List available Ollama models."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{OLLAMA_URL}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Failed to list Ollama models: {e}")
        return []

    async def health_check(self) -> bool:
        """Check if Ollama is running."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{OLLAMA_URL}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


def get_ollama_provider() -> Optional[OllamaProvider]:
    """Get Ollama provider if enabled."""
    if not OLLAMA_ENABLED:
        return None
    provider = OllamaProvider()
    return provider if provider.is_available else None
