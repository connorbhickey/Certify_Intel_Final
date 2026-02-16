"""
Certify Intel - LiteLLM Provider Tests

Tests for the LiteLLM unified AI gateway provider.

Run: python -m pytest -xvs tests/test_litellm_provider.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestLiteLLMProviderConfig:
    """Test LiteLLM provider configuration and defaults."""

    def test_disabled_by_default(self, monkeypatch):
        """Provider should be disabled when LITELLM_ENABLED is not set."""
        monkeypatch.delenv("LITELLM_ENABLED", raising=False)
        # Re-import to pick up env var
        import importlib
        import litellm_provider
        importlib.reload(litellm_provider)
        assert litellm_provider.LITELLM_ENABLED is False

    def test_get_litellm_provider_returns_none_when_disabled(self, monkeypatch):
        """get_litellm_provider() should return None when disabled."""
        monkeypatch.setenv("LITELLM_ENABLED", "false")
        import importlib
        import litellm_provider
        importlib.reload(litellm_provider)
        result = litellm_provider.get_litellm_provider()
        assert result is None

    def test_default_proxy_url(self, monkeypatch):
        """Default proxy URL should be http://localhost:4000."""
        monkeypatch.delenv("LITELLM_PROXY_URL", raising=False)
        import importlib
        import litellm_provider
        importlib.reload(litellm_provider)
        assert litellm_provider.LITELLM_PROXY_URL == "http://localhost:4000"

    def test_custom_proxy_url(self, monkeypatch):
        """Custom proxy URL should be read from env."""
        monkeypatch.setenv("LITELLM_PROXY_URL", "http://myproxy:5000")
        import importlib
        import litellm_provider
        importlib.reload(litellm_provider)
        assert litellm_provider.LITELLM_PROXY_URL == "http://myproxy:5000"


class TestLiteLLMProviderClass:
    """Test LiteLLMProvider class methods."""

    def test_instantiation(self):
        """LiteLLMProvider should instantiate without errors."""
        from litellm_provider import LiteLLMProvider
        provider = LiteLLMProvider()
        assert provider._client is None

    @pytest.mark.asyncio
    async def test_generate_calls_openai_client(self):
        """generate() should call the OpenAI-compatible client."""
        from litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider()
        provider.is_available = True

        mock_usage = MagicMock()
        mock_usage.completion_tokens = 50
        mock_usage.prompt_tokens = 20

        mock_choice = MagicMock()
        mock_choice.message.content = "Test response"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )
        provider._client = mock_client

        result = await provider.generate(
            prompt="Hello",
            model="gpt-4o",
            system_prompt="You are helpful",
        )

        assert result["response"] == "Test response"
        assert result["tokens_input"] == 20
        assert result["tokens_output"] == 50
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_raises_when_no_client(self):
        """generate() should raise RuntimeError when client unavailable."""
        from litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider()
        provider.is_available = False

        # Mock _get_client to return None (simulating missing openai pkg)
        with patch.object(provider, '_get_client', return_value=None):
            with pytest.raises(RuntimeError, match="not available"):
                await provider.generate(prompt="Hello")

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self):
        """health_check() should return False when proxy unreachable."""
        from litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider()

        # httpx is imported locally inside health_check(), so patch the module
        mock_httpx = MagicMock()
        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__ = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        mock_httpx.AsyncClient.return_value = mock_client_ctx

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = await provider.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_healthy(self):
        """health_check() should return True when proxy responds 200."""
        from litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider()

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_resp)

        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__ = AsyncMock(
            return_value=mock_client_instance
        )
        mock_client_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client_ctx

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_generate_includes_system_prompt_in_messages(self):
        """generate() should include system prompt as first message."""
        from litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider()
        provider.is_available = True

        mock_usage = MagicMock()
        mock_usage.completion_tokens = 10
        mock_usage.prompt_tokens = 5

        mock_choice = MagicMock()
        mock_choice.message.content = "Response"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )
        provider._client = mock_client

        await provider.generate(
            prompt="Hello",
            system_prompt="You are a helpful assistant"
        )

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get(
            "messages", call_kwargs[1].get("messages", [])
        ) if call_kwargs.kwargs else call_kwargs[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_generate_without_system_prompt(self):
        """generate() without system_prompt should only have user message."""
        from litellm_provider import LiteLLMProvider

        provider = LiteLLMProvider()
        provider.is_available = True

        mock_usage = MagicMock()
        mock_usage.completion_tokens = 10
        mock_usage.prompt_tokens = 5

        mock_choice = MagicMock()
        mock_choice.message.content = "Response"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )
        provider._client = mock_client

        await provider.generate(prompt="Hello")

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get(
            "messages", call_kwargs[1].get("messages", [])
        ) if call_kwargs.kwargs else call_kwargs[1]["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_get_litellm_provider_returns_instance_when_enabled(
        self, monkeypatch
    ):
        """get_litellm_provider() should return LiteLLMProvider when enabled."""
        monkeypatch.setenv("LITELLM_ENABLED", "true")
        import importlib
        import litellm_provider
        importlib.reload(litellm_provider)
        result = litellm_provider.get_litellm_provider()
        assert result is not None
        assert isinstance(result, litellm_provider.LiteLLMProvider)
