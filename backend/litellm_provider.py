"""
Certify Intel - LiteLLM Unified AI Gateway Provider
====================================================
Routes AI requests through LiteLLM proxy for unified cost tracking,
rate limiting, and load balancing across 100+ LLM providers.

Config:
    LITELLM_ENABLED=false (default OFF)
    LITELLM_PROXY_URL=http://localhost:4000
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

LITELLM_ENABLED = os.getenv("LITELLM_ENABLED", "false").lower() == "true"
LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL", "http://localhost:4000")


class LiteLLMProvider:
    """Unified LLM gateway via LiteLLM proxy."""

    def __init__(self):
        self._client = None
        self.is_available = LITELLM_ENABLED

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key="sk-litellm",  # LiteLLM proxy uses any key
                    base_url=f"{LITELLM_PROXY_URL}/v1"
                )
            except ImportError:
                logger.warning("openai package required for LiteLLM provider")
                self.is_available = False
        return self._client

    async def generate(
        self,
        prompt: str,
        model: str = "gpt-4o",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate via LiteLLM proxy."""
        client = self._get_client()
        if not client:
            raise RuntimeError("LiteLLM client not available")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=model,
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
        }

    async def health_check(self) -> bool:
        """Check if LiteLLM proxy is reachable."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{LITELLM_PROXY_URL}/health")
                return resp.status_code == 200
        except Exception:
            return False


def get_litellm_provider() -> Optional[LiteLLMProvider]:
    """Get LiteLLM provider if enabled."""
    if not LITELLM_ENABLED:
        return None
    provider = LiteLLMProvider()
    return provider if provider.is_available else None
