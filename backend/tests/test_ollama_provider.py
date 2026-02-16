"""
Certify Intel - Ollama Provider Tests

Tests for the Ollama local LLM provider.

Run: python -m pytest -xvs tests/test_ollama_provider.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestOllamaProviderConfig:
    """Test Ollama provider configuration and defaults."""

    def test_disabled_by_default(self, monkeypatch):
        """Provider should be disabled when OLLAMA_ENABLED is not set."""
        monkeypatch.delenv("OLLAMA_ENABLED", raising=False)
        import importlib
        import ollama_provider
        importlib.reload(ollama_provider)
        assert ollama_provider.OLLAMA_ENABLED is False

    def test_get_ollama_provider_returns_none_when_disabled(self, monkeypatch):
        """get_ollama_provider() should return None when disabled."""
        monkeypatch.setenv("OLLAMA_ENABLED", "false")
        import importlib
        import ollama_provider
        importlib.reload(ollama_provider)
        result = ollama_provider.get_ollama_provider()
        assert result is None

    def test_default_url(self, monkeypatch):
        """Default URL should be http://localhost:11434."""
        monkeypatch.delenv("OLLAMA_URL", raising=False)
        import importlib
        import ollama_provider
        importlib.reload(ollama_provider)
        assert ollama_provider.OLLAMA_URL == "http://localhost:11434"

    def test_default_model(self, monkeypatch):
        """Default model should be llama3.1:8b."""
        monkeypatch.delenv("OLLAMA_DEFAULT_MODEL", raising=False)
        import importlib
        import ollama_provider
        importlib.reload(ollama_provider)
        assert ollama_provider.OLLAMA_DEFAULT_MODEL == "llama3.1:8b"

    def test_custom_model(self, monkeypatch):
        """Custom model should be read from env."""
        monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "mistral:7b")
        import importlib
        import ollama_provider
        importlib.reload(ollama_provider)
        assert ollama_provider.OLLAMA_DEFAULT_MODEL == "mistral:7b"


class TestOllamaProviderClass:
    """Test OllamaProvider class methods."""

    def test_instantiation(self):
        """OllamaProvider should instantiate without errors."""
        from ollama_provider import OllamaProvider
        provider = OllamaProvider()
        assert provider._client is None

    @pytest.mark.asyncio
    async def test_generate_uses_default_model(self):
        """generate() should use default model when none specified."""
        from ollama_provider import OllamaProvider

        provider = OllamaProvider()
        provider.is_available = True
        provider.default_model = "llama3.1:8b"

        mock_usage = MagicMock()
        mock_usage.completion_tokens = 30
        mock_usage.prompt_tokens = 15

        mock_choice = MagicMock()
        mock_choice.message.content = "Ollama response"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )
        provider._client = mock_client

        result = await provider.generate(prompt="Hello")

        assert result["response"] == "Ollama response"
        assert result["tokens_input"] == 15
        assert result["tokens_output"] == 30
        assert result["model"] == "llama3.1:8b"

    @pytest.mark.asyncio
    async def test_generate_uses_specified_model(self):
        """generate() should use the specified model."""
        from ollama_provider import OllamaProvider

        provider = OllamaProvider()
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

        result = await provider.generate(
            prompt="Hello", model="mistral:7b"
        )

        assert result["model"] == "mistral:7b"
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "mistral:7b"

    @pytest.mark.asyncio
    async def test_generate_raises_when_no_client(self):
        """generate() should raise RuntimeError when client unavailable."""
        from ollama_provider import OllamaProvider

        provider = OllamaProvider()
        provider.is_available = False

        # Mock _get_client to return None (simulating missing openai pkg)
        with patch.object(provider, '_get_client', return_value=None):
            with pytest.raises(RuntimeError, match="not available"):
                await provider.generate(prompt="Hello")

    @pytest.mark.asyncio
    async def test_list_models_returns_model_names(self):
        """list_models() should return list of model name strings."""
        from ollama_provider import OllamaProvider

        provider = OllamaProvider()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "mistral:7b"},
            ]
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_resp)

        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__ = AsyncMock(
            return_value=mock_client_instance
        )
        mock_client_ctx.__aexit__ = AsyncMock(return_value=None)

        # httpx is imported locally, so patch via sys.modules
        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client_ctx

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            models = await provider.list_models()

        assert models == ["llama3.1:8b", "mistral:7b"]

    @pytest.mark.asyncio
    async def test_list_models_returns_empty_on_error(self):
        """list_models() should return empty list on connection error."""
        from ollama_provider import OllamaProvider

        provider = OllamaProvider()

        mock_httpx = MagicMock()
        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__ = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        mock_httpx.AsyncClient.return_value = mock_client_ctx

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            models = await provider.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self):
        """health_check() should return False when Ollama unreachable."""
        from ollama_provider import OllamaProvider

        provider = OllamaProvider()

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
        """health_check() should return True when Ollama responds 200."""
        from ollama_provider import OllamaProvider

        provider = OllamaProvider()

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
    async def test_generate_includes_system_prompt(self):
        """generate() with system_prompt should include it in messages."""
        from ollama_provider import OllamaProvider

        provider = OllamaProvider()
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
            system_prompt="You are a healthcare AI"
        )

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get(
            "messages", call_kwargs[1].get("messages", [])
        ) if call_kwargs.kwargs else call_kwargs[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_generate_fallback_token_count_when_no_usage(self):
        """generate() should estimate tokens when usage is None."""
        from ollama_provider import OllamaProvider

        provider = OllamaProvider()
        provider.is_available = True

        mock_choice = MagicMock()
        mock_choice.message.content = "short response"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )
        provider._client = mock_client

        result = await provider.generate(prompt="Hello world test")

        assert result["response"] == "short response"
        # Fallback counts words: "short response" = 2
        assert result["tokens_output"] == 2
        # Fallback counts words in prompt: "Hello world test" = 3
        assert result["tokens_input"] == 3

    def test_get_ollama_provider_returns_instance_when_enabled(
        self, monkeypatch
    ):
        """get_ollama_provider() should return OllamaProvider when enabled."""
        monkeypatch.setenv("OLLAMA_ENABLED", "true")
        import importlib
        import ollama_provider
        importlib.reload(ollama_provider)
        result = ollama_provider.get_ollama_provider()
        assert result is not None
        assert isinstance(result, ollama_provider.OllamaProvider)
