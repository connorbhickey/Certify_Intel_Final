"""
Certify Intel - Hybrid AI Integration Tests (v5.0.6)
Tests for hybrid AI routing between OpenAI and Gemini providers.

Run with: pytest tests/test_hybrid_integration.py -v
"""

import os
import sys
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_provider import AIRouter, GeminiProvider, AIResponse


# ============== TEST FIXTURES ==============

@pytest.fixture
def mock_genai():
    """Mock the google.genai module (new unified SDK)."""
    with patch("gemini_provider.genai") as mock_module:
        mock_client = MagicMock()
        mock_module.Client.return_value = mock_client
        mock_module._mock_client = mock_client
        yield mock_module


@pytest.fixture
def mock_openai():
    """Mock the OpenAI module."""
    with patch("gemini_provider.OpenAI") as mock:
        yield mock


@pytest.fixture
def hybrid_env():
    """Environment with both providers available."""
    return {
        "AI_PROVIDER": "hybrid",
        "AI_FALLBACK_ENABLED": "true",
        "GOOGLE_AI_API_KEY": "test-gemini-key",
        "OPENAI_API_KEY": "test-openai-key",
        "AI_BULK_TASKS": "gemini",
        "AI_QUALITY_TASKS": "openai",
    }


@pytest.fixture
def gemini_only_env():
    """Environment with only Gemini available."""
    return {
        "AI_PROVIDER": "gemini",
        "GOOGLE_AI_API_KEY": "test-gemini-key",
        "OPENAI_API_KEY": "",
    }


@pytest.fixture
def openai_only_env():
    """Environment with only OpenAI available."""
    return {
        "AI_PROVIDER": "openai",
        "GOOGLE_AI_API_KEY": "",
        "OPENAI_API_KEY": "test-openai-key",
    }


# ============== HYBRID ROUTING TESTS ==============

class TestHybridRouting:
    """Tests for hybrid AI routing logic."""

    def test_hybrid_mode_routes_bulk_to_gemini(self, mock_genai, hybrid_env):
        """Test that bulk tasks are routed to Gemini in hybrid mode."""

        with patch.dict(os.environ, hybrid_env, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = True
            router.openai_available = True

            # Bulk extraction should go to Gemini
            assert router.get_provider("bulk_extraction") == "gemini"
            assert router.get_provider("news_analysis") == "gemini"

    def test_hybrid_mode_routes_quality_to_openai(self, mock_genai, hybrid_env):
        """Test that quality tasks are routed to OpenAI in hybrid mode."""

        with patch.dict(os.environ, hybrid_env, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = True
            router.openai_available = True

            # Quality tasks should go to OpenAI
            assert router.get_provider("executive_summary") == "openai"
            assert router.get_provider("complex_reasoning") == "openai"

    def test_fallback_to_openai_when_gemini_unavailable(self, mock_genai, hybrid_env):
        """Test fallback to OpenAI when Gemini is unavailable."""

        with patch.dict(os.environ, hybrid_env, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = False  # Gemini unavailable
            router.openai_available = True

            # Should fall back to OpenAI
            provider = router.get_provider("bulk_extraction")
            assert provider == "openai"

    def test_fallback_to_gemini_when_openai_unavailable(self, mock_genai, hybrid_env):
        """Test fallback to Gemini when OpenAI is unavailable."""

        with patch.dict(os.environ, hybrid_env, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = True
            router.openai_available = False  # OpenAI unavailable

            # Quality tasks should fall back to Gemini
            provider = router.get_provider("executive_summary")
            assert provider == "gemini"

    def test_no_fallback_when_disabled(self, mock_genai):
        """Test that fallback is disabled when AI_FALLBACK_ENABLED is false."""

        env = {
            "AI_PROVIDER": "hybrid",
            "AI_FALLBACK_ENABLED": "false",
            "AI_BULK_TASKS": "gemini",
            "GOOGLE_AI_API_KEY": "",
            "OPENAI_API_KEY": "test-key",
        }

        with patch.dict(os.environ, env, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = False
            router.openai_available = True

            # Should return "none" instead of falling back
            provider = router.get_provider("bulk_extraction")
            assert provider == "none"


# ============== PROVIDER SELECTION TESTS ==============

class TestProviderSelection:
    """Tests for provider selection in different scenarios."""

    def test_gemini_only_mode(self, mock_genai, gemini_only_env):
        """Test Gemini-only mode."""

        with patch.dict(os.environ, gemini_only_env, clear=True):
            router = AIRouter()

            # All tasks should go to Gemini
            assert router.routing_config["bulk_extraction"] == "gemini"
            assert router.routing_config["executive_summary"] == "gemini"
            assert router.routing_config["chat_response"] == "gemini"

    def test_openai_only_mode(self, mock_genai, openai_only_env):
        """Test OpenAI-only mode."""

        with patch.dict(os.environ, openai_only_env, clear=True):
            router = AIRouter()

            # All tasks should go to OpenAI
            assert router.routing_config["bulk_extraction"] == "openai"
            assert router.routing_config["executive_summary"] == "openai"
            assert router.routing_config["chat_response"] == "openai"

    def test_auto_routing_prefers_gemini(self, mock_genai):
        """Test that 'auto' routing prefers Gemini (cheaper)."""

        env = {
            "AI_PROVIDER": "hybrid",
            "GOOGLE_AI_API_KEY": "test-key",
            "OPENAI_API_KEY": "test-key",
        }

        with patch.dict(os.environ, env, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = True
            router.openai_available = True

            # Default routing should prefer Gemini for auto
            router.routing_config["test_task"] = "auto"
            provider = router.get_provider("test_task")
            assert provider == "gemini"


# ============== REQUEST ROUTING TESTS ==============

class TestRequestRouting:
    """Tests for actual request routing."""

    def test_route_request_to_gemini(self, mock_genai):
        """Test routing a request to Gemini."""
        mock_client = mock_genai._mock_client
        mock_response = Mock()
        mock_response.text = "Gemini response"
        mock_client.models.generate_content.return_value = mock_response

        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test-key"}, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = True
            router.gemini.generate_text = Mock(return_value=AIResponse(
                content="Gemini response",
                model="gemini-2.5-flash",
                provider="gemini",
                tokens_used=100,
                cost_estimate=0.001,
                latency_ms=500,
                success=True
            ))
            router.openai_available = False

            response = router.route_request(
                task_type="bulk_extraction",
                prompt="Extract data",
            )

            assert response.provider == "gemini"
            assert response.success is True

    def test_route_request_no_providers(self, mock_genai):
        """Test routing when no providers are available."""

        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "", "OPENAI_API_KEY": ""}, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = False
            router.openai_available = False

            response = router.route_request(
                task_type="any_task",
                prompt="Test prompt",
            )

            assert response.success is False
            assert "No AI provider available" in response.error

    def test_route_json_request(self, mock_genai):
        """Test routing a JSON request."""

        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test-key"}, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = True
            router.gemini.generate_json = Mock(return_value={
                "key": "value",
                "_provider": "gemini",
                "_model": "gemini-2.5-flash",
                "_cost": 0.001
            })
            router.openai_available = False

            response = router.route_request(
                task_type="data_extraction",
                prompt="Extract data as JSON",
                require_json=True
            )

            assert response.provider == "gemini"


# ============== ENVIRONMENT CONFIGURATION TESTS ==============

class TestEnvironmentConfig:
    """Tests for environment-based configuration."""

    def test_ai_bulk_tasks_override(self, mock_genai):
        """Test AI_BULK_TASKS environment override."""

        env = {
            "AI_PROVIDER": "hybrid",
            "AI_BULK_TASKS": "openai",  # Force bulk to OpenAI
            "GOOGLE_AI_API_KEY": "test",
            "OPENAI_API_KEY": "test",
        }

        with patch.dict(os.environ, env, clear=True):
            router = AIRouter()

            # Bulk tasks should be forced to OpenAI
            assert router.routing_config["bulk_extraction"] == "openai"
            assert router.routing_config["news_analysis"] == "openai"

    def test_ai_quality_tasks_override(self, mock_genai):
        """Test AI_QUALITY_TASKS environment override."""

        env = {
            "AI_PROVIDER": "hybrid",
            "AI_QUALITY_TASKS": "gemini",  # Force quality to Gemini
            "GOOGLE_AI_API_KEY": "test",
            "OPENAI_API_KEY": "test",
        }

        with patch.dict(os.environ, env, clear=True):
            router = AIRouter()

            # Quality tasks should be forced to Gemini
            assert router.routing_config["executive_summary"] == "gemini"
            assert router.routing_config["complex_reasoning"] == "gemini"

    def test_model_override(self, mock_genai):
        """Test GOOGLE_AI_MODEL environment override."""

        env = {
            "GOOGLE_AI_API_KEY": "test",
            "GOOGLE_AI_MODEL": "gemini-2.5-pro",
        }

        with patch.dict(os.environ, env, clear=True):
            provider = GeminiProvider()
            assert provider.config.model == "gemini-2.5-pro"


# ============== TASK TYPE ROUTING TESTS ==============

class TestTaskTypeRouting:
    """Tests for routing based on task types."""

    def test_all_task_types_have_routing(self, mock_genai):
        """Test that all expected task types have routing config."""

        router = AIRouter()

        expected_tasks = [
            "bulk_extraction",
            "data_extraction",
            "executive_summary",
            "chat_response",
            "news_analysis",
            "classification",
            "complex_reasoning",
        ]

        for task in expected_tasks:
            assert task in router.routing_config

    def test_unknown_task_type_uses_auto(self, mock_genai):
        """Test that unknown task types use auto routing."""

        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test"}, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = True
            router.openai_available = True

            # Unknown task should default to auto (which prefers Gemini)
            provider = router.get_provider("unknown_task_type")
            assert provider == "gemini"


# ============== INTEGRATION SCENARIO TESTS ==============

class TestIntegrationScenarios:
    """End-to-end integration scenario tests."""

    def test_executive_summary_workflow(self, mock_genai):
        """Test executive summary generation workflow."""
        mock_client = mock_genai._mock_client
        mock_response = Mock()
        mock_response.text = "Executive summary: The competitive landscape shows..."
        mock_client.models.generate_content.return_value = mock_response

        with patch.dict(os.environ, {
            "AI_PROVIDER": "hybrid",
            "GOOGLE_AI_API_KEY": "test",
            "OPENAI_API_KEY": "",
        }, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = True
            router.gemini.generate_text = Mock(return_value=AIResponse(
                content="Executive summary text",
                model="gemini-2.5-flash",
                provider="gemini",
                tokens_used=500,
                cost_estimate=0.005,
                latency_ms=1000,
                success=True
            ))

            response = router.route_request(
                task_type="executive_summary",
                prompt="Generate executive summary for competitors: A, B, C",
                system_prompt="You are a strategic analyst."
            )

            # Should succeed with Gemini fallback
            assert response.success is True

    def test_bulk_extraction_cost_efficiency(self, mock_genai):
        """Test that bulk extraction uses cost-efficient model."""

        with patch.dict(os.environ, {
            "AI_PROVIDER": "hybrid",
            "GOOGLE_AI_API_KEY": "test",
        }, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = True

            # Bulk extraction should route to Gemini (cheaper)
            provider = router.get_provider("bulk_extraction")
            assert provider == "gemini"

            # Verify recommended model is flash (cheapest for bulk)
            gemini = GeminiProvider()
            model = gemini.get_recommended_model("bulk_extraction")
            assert model == "gemini-3-flash-preview"

    def test_graceful_degradation(self, mock_genai):
        """Test graceful degradation when both providers fail."""

        with patch.dict(os.environ, {
            "AI_PROVIDER": "hybrid",
            "AI_FALLBACK_ENABLED": "true",
            "GOOGLE_AI_API_KEY": "",
            "OPENAI_API_KEY": "",
        }, clear=True):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = False
            router.openai_available = False

            response = router.route_request(
                task_type="data_extraction",
                prompt="Extract data"
            )

            # Should fail gracefully with informative error
            assert response.success is False
            assert "No AI provider" in response.error


# ============== RUN TESTS ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
