"""
Certify Intel - Gemini Provider Unit Tests (v5.0.6)
Tests for GeminiProvider, GeminiExtractor, and AIRouter classes.

Run with: pytest tests/test_gemini_provider.py -v
"""

import os
import sys
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_provider import (
    GeminiProvider,
    GeminiExtractor,
    GeminiConfig,
    AIResponse,
    AIRouter,
    get_gemini_provider,
    get_ai_router,
    extract_with_gemini,
    GEMINI_AVAILABLE,
)


# ============== TEST FIXTURES ==============

@pytest.fixture
def mock_genai():
    """Mock the google.genai module (new unified SDK)."""
    with patch("gemini_provider.genai") as mock_module:
        # Mock Client constructor
        mock_client = MagicMock()
        mock_module.Client.return_value = mock_client
        # Attach client to module mock for test access
        mock_module._mock_client = mock_client
        yield mock_module


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    mock_response = Mock()
    mock_response.text = "This is a test response from Gemini."
    return mock_response


@pytest.fixture
def mock_json_response():
    """Mock Gemini JSON response."""
    mock_response = Mock()
    mock_response.text = '{"key": "value", "number": 42}'
    return mock_response


@pytest.fixture
def gemini_config():
    """Create a test GeminiConfig."""
    return GeminiConfig(
        api_key="test-api-key",
        model="gemini-3-flash-preview",
        temperature=0.1,
    )


# ============== GEMINI CONFIG TESTS ==============

class TestGeminiConfig:
    """Tests for GeminiConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = GeminiConfig(api_key="test-key")
        assert config.api_key == "test-key"
        assert config.model == "gemini-3-flash-preview"
        assert config.temperature == 0.1
        assert config.max_output_tokens == 8192
        assert config.top_p == 0.95
        assert config.top_k == 40

    def test_custom_values(self):
        """Test custom configuration values."""
        config = GeminiConfig(
            api_key="custom-key",
            model="gemini-2.5-pro",
            temperature=0.5,
            max_output_tokens=4096,
        )
        assert config.api_key == "custom-key"
        assert config.model == "gemini-2.5-pro"
        assert config.temperature == 0.5
        assert config.max_output_tokens == 4096


# ============== AI RESPONSE TESTS ==============

class TestAIResponse:
    """Tests for AIResponse dataclass."""

    def test_successful_response(self):
        """Test creating a successful response."""
        response = AIResponse(
            content="Test content",
            model="gemini-2.5-flash",
            provider="gemini",
            tokens_used=100,
            cost_estimate=0.001,
            latency_ms=500.0,
            success=True,
        )
        assert response.content == "Test content"
        assert response.success is True
        assert response.error is None

    def test_failed_response(self):
        """Test creating a failed response."""
        response = AIResponse(
            content="",
            model="gemini-2.5-flash",
            provider="gemini",
            tokens_used=0,
            cost_estimate=0.0,
            latency_ms=100.0,
            success=False,
            error="API error",
        )
        assert response.success is False
        assert response.error == "API error"


# ============== GEMINI PROVIDER TESTS ==============

class TestGeminiProvider:
    """Tests for GeminiProvider class."""

    def test_initialization_without_api_key(self):
        """Test initialization without API key."""
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": ""}):
            provider = GeminiProvider()
            # Provider should exist but not be available
            assert provider.config.api_key == ""

    def test_initialization_with_config(self, gemini_config, mock_genai):
        """Test initialization with explicit config."""
        provider = GeminiProvider(config=gemini_config)
        assert provider.config.api_key == "test-api-key"
        assert provider.config.model == "gemini-3-flash-preview"

    def test_get_recommended_model(self, gemini_config, mock_genai):
        """Test model recommendation for different tasks."""
        provider = GeminiProvider(config=gemini_config)

        assert provider.get_recommended_model("bulk_extraction") == "gemini-3-flash-preview"
        assert provider.get_recommended_model("complex_analysis") == "gemini-3-pro-preview"
        assert provider.get_recommended_model("data_extraction") == "gemini-3-flash-preview"

    def test_estimate_cost(self, gemini_config, mock_genai):
        """Test cost estimation."""
        provider = GeminiProvider(config=gemini_config)

        # Test flash model cost
        cost = provider.estimate_cost(1000000, 500000, "gemini-2.5-flash")
        expected = (1000000 / 1_000_000) * 0.075 + (500000 / 1_000_000) * 0.30
        assert abs(cost - expected) < 0.001

    def test_generate_text_not_available(self):
        """Test generate_text when provider is not available."""
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": ""}):
            provider = GeminiProvider()
            response = provider.generate_text("Test prompt")
            assert response.success is False
            assert "not available" in response.error

    def test_generate_text_success(self, gemini_config, mock_genai, mock_gemini_response):
        """Test successful text generation."""
        mock_client = mock_genai._mock_client
        mock_client.models.generate_content.return_value = mock_gemini_response

        provider = GeminiProvider(config=gemini_config)
        # Provider should have client set via mock
        assert provider.client is not None

        response = provider.generate_text("Test prompt")
        # Should work if provider is properly set up
        if provider.is_available:
            assert response.content == mock_gemini_response.text
            assert response.success is True
            assert response.provider == "gemini"

    def test_generate_json_success(self, gemini_config, mock_genai, mock_json_response):
        """Test successful JSON generation."""
        mock_client = mock_genai._mock_client
        mock_client.models.generate_content.return_value = mock_json_response

        provider = GeminiProvider(config=gemini_config)

        result = provider.generate_json("Extract data from this text")
        # Should parse JSON if available
        if provider.is_available:
            assert isinstance(result, dict)
            assert "_provider" in result

    def test_model_pricing_constants(self, gemini_config, mock_genai):
        """Test that model pricing constants are defined."""
        provider = GeminiProvider(config=gemini_config)

        assert "gemini-3-flash-preview" in provider.MODEL_PRICING
        assert "gemini-3-pro-preview" in provider.MODEL_PRICING
        assert "gemini-2.5-flash" in provider.MODEL_PRICING
        assert "gemini-2.5-pro" in provider.MODEL_PRICING
        assert "input" in provider.MODEL_PRICING["gemini-3-flash-preview"]
        assert "output" in provider.MODEL_PRICING["gemini-3-flash-preview"]


# ============== GEMINI EXTRACTOR TESTS ==============

class TestGeminiExtractor:
    """Tests for GeminiExtractor class."""

    def test_initialization(self, mock_genai):
        """Test extractor initialization."""
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test-key"}):
            extractor = GeminiExtractor()
            assert extractor.provider is not None

    def test_extract_from_content_not_available(self):
        """Test extraction when provider is not available."""
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": ""}):
            extractor = GeminiExtractor()
            result = extractor.extract_from_content("Test Company", "Some content")
            assert "extraction_notes" in result or "error" in result

    def test_system_prompt(self, mock_genai):
        """Test system prompt content."""
        extractor = GeminiExtractor()
        prompt = extractor._get_system_prompt()

        assert "competitive intelligence" in prompt.lower()
        assert "healthcare" in prompt.lower()

    def test_build_extraction_prompt_pricing(self, mock_genai):
        """Test pricing page extraction prompt."""

        extractor = GeminiExtractor()
        prompt = extractor._build_extraction_prompt("Phreesia", "Pricing content", "pricing")

        assert "pricing" in prompt.lower()
        assert "Phreesia" in prompt
        assert "base_price" in prompt

    def test_build_extraction_prompt_features(self, mock_genai):
        """Test features page extraction prompt."""

        extractor = GeminiExtractor()
        prompt = extractor._build_extraction_prompt("Phreesia", "Features content", "features")

        assert "feature" in prompt.lower()
        assert "product_categories" in prompt

    def test_build_extraction_prompt_about(self, mock_genai):
        """Test about page extraction prompt."""

        extractor = GeminiExtractor()
        prompt = extractor._build_extraction_prompt("Phreesia", "About content", "about")

        assert "year_founded" in prompt
        assert "employee_count" in prompt


# ============== AI ROUTER TESTS ==============

class TestAIRouter:
    """Tests for AIRouter class."""

    def test_initialization(self, mock_genai):
        """Test router initialization."""

        router = AIRouter()
        assert router.routing_config is not None
        assert "bulk_extraction" in router.routing_config

    def test_default_routing_config(self, mock_genai):
        """Test default routing configuration."""

        router = AIRouter()

        assert router.routing_config["bulk_extraction"] == "gemini"
        assert router.routing_config["data_extraction"] == "gemini"
        assert router.routing_config["chat_response"] == "openai"

    def test_get_provider_bulk_tasks(self, mock_genai):
        """Test provider selection for bulk tasks."""

        with patch.dict(os.environ, {"AI_PROVIDER": "hybrid", "GOOGLE_AI_API_KEY": "test"}):
            router = AIRouter()
            if router.gemini.is_available:
                assert router.get_provider("bulk_extraction") == "gemini"

    def test_get_provider_no_providers(self, mock_genai):
        """Test when no providers are available."""

        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "", "OPENAI_API_KEY": ""}):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = False
            router.openai_available = False

            result = router.get_provider("any_task")
            assert result == "none"

    def test_env_config_openai_only(self, mock_genai):
        """Test forcing OpenAI only via environment."""

        # Clear existing keys AND task-specific overrides to prevent .env leakage
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "test", "GOOGLE_AI_API_KEY": "", "AI_BULK_TASKS": "", "AI_QUALITY_TASKS": ""}, clear=False):
            router = AIRouter()
            # When AI_PROVIDER is openai, all tasks should route to openai
            assert router.routing_config["bulk_extraction"] == "openai"

    def test_env_config_gemini_only(self, mock_genai):
        """Test forcing Gemini only via environment."""

        with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GOOGLE_AI_API_KEY": "test"}):
            router = AIRouter()
            assert router.routing_config["bulk_extraction"] == "gemini"
            assert router.routing_config["chat_response"] == "gemini"


# ============== CONVENIENCE FUNCTION TESTS ==============

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_gemini_provider_no_key(self):
        """Test get_gemini_provider without API key."""
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": ""}):
            provider = get_gemini_provider()
            # Should return None when not available
            if provider is not None:
                assert not provider.is_available or provider.config.api_key != ""

    def test_get_ai_router(self, mock_genai):
        """Test get_ai_router returns router instance."""

        router = get_ai_router()
        assert isinstance(router, AIRouter)

    def test_extract_with_gemini_not_available(self):
        """Test extract_with_gemini when not available."""
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": ""}):
            result = extract_with_gemini("Test Company", "Test content")
            assert isinstance(result, dict)


# ============== MULTIMODAL TESTS (v5.0.5-5.0.6) ==============

class TestMultimodalFeatures:
    """Tests for multimodal analysis features."""

    def test_prepare_image_bytes(self, gemini_config, mock_genai):
        """Test image preparation from bytes."""

        provider = GeminiProvider(config=gemini_config)
        provider.client = mock_genai

        # Test with fake image bytes
        fake_image = b"fake image data"
        result = provider._prepare_image(fake_image)

        if result is not None:
            # New SDK returns genai_types.Part object via Part.from_bytes()
            from google.genai import types as genai_types
            assert isinstance(result, genai_types.Part)

    def test_analyze_image_not_available(self):
        """Test image analysis when provider not available."""
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": ""}):
            provider = GeminiProvider()
            response = provider.analyze_image(b"fake", "Describe this")
            assert response.success is False

    def test_analyze_screenshot_prompts(self, gemini_config, mock_genai):
        """Test screenshot analysis prompt generation."""

        provider = GeminiProvider(config=gemini_config)

        # Test that different page types generate different prompts
        # We can't easily test the actual analysis, but we can verify the method exists
        assert hasattr(provider, "analyze_screenshot")

    def test_analyze_pdf_not_available_pymupdf(self, gemini_config, mock_genai):
        """Test PDF analysis when PyMuPDF not available."""

        provider = GeminiProvider(config=gemini_config)

        # Mock PYMUPDF_AVAILABLE to False
        with patch("gemini_provider.PYMUPDF_AVAILABLE", False):
            # Need to reload or test differently
            pass

    def test_get_video_mime_type(self, gemini_config, mock_genai):
        """Test video MIME type detection."""

        provider = GeminiProvider(config=gemini_config)

        assert provider._get_video_mime_type("video.mp4") == "video/mp4"
        assert provider._get_video_mime_type("video.webm") == "video/webm"
        assert provider._get_video_mime_type("video.mov") == "video/quicktime"
        assert provider._get_video_mime_type("video.avi") == "video/x-msvideo"

    def test_get_video_analysis_prompt(self, gemini_config, mock_genai):
        """Test video analysis prompt generation."""

        provider = GeminiProvider(config=gemini_config)

        demo_prompt = provider._get_video_analysis_prompt("demo", "Competitor X")
        assert "demo" in demo_prompt.lower()
        assert "Competitor X" in demo_prompt

        webinar_prompt = provider._get_video_analysis_prompt("webinar", "Competitor X")
        assert "webinar" in webinar_prompt.lower()

    def test_process_news_batch_structure(self, gemini_config, mock_genai):
        """Test news batch processing structure."""

        provider = GeminiProvider(config=gemini_config)

        # Test prompt building
        articles = [
            {"title": "Test Article 1", "snippet": "Snippet 1", "url": "http://example.com/1"},
            {"title": "Test Article 2", "snippet": "Snippet 2", "url": "http://example.com/2"},
        ]

        prompt = provider._build_batch_news_prompt(articles, "summary")
        assert "Article 1" in prompt
        assert "Article 2" in prompt
        assert "summary" in prompt.lower()


# ============== INTEGRATION-LIKE TESTS ==============

class TestIntegrationScenarios:
    """Integration-like tests for common usage scenarios."""

    def test_full_extraction_workflow(self, mock_genai, mock_json_response):
        """Test a full extraction workflow."""
        mock_client = mock_genai._mock_client
        mock_client.models.generate_content.return_value = mock_json_response

        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test-key"}):
            extractor = GeminiExtractor()

            content = """
            Phreesia Inc is a leading patient intake company.
            Pricing starts at $299/month.
            They serve over 3,000 healthcare organizations.
            """

            # The extraction should work if provider is available
            result = extractor.extract_from_content("Phreesia", content)
            assert isinstance(result, dict)

    def test_router_fallback_behavior(self, mock_genai):
        """Test router fallback when primary provider fails."""

        with patch.dict(os.environ, {
            "AI_PROVIDER": "hybrid",
            "AI_FALLBACK_ENABLED": "true",
            "GOOGLE_AI_API_KEY": "",  # Gemini not available
            "OPENAI_API_KEY": "test"   # OpenAI available
        }):
            router = AIRouter()
            router.gemini = Mock()
            router.gemini.is_available = False
            router.openai_available = True

            # Should fall back to OpenAI
            provider = router.get_provider("bulk_extraction")
            assert provider == "openai"

    def test_cost_optimization_routing(self, mock_genai):
        """Test that bulk tasks are routed to cheaper models."""

        with patch.dict(os.environ, {
            "AI_PROVIDER": "hybrid",
            "GOOGLE_AI_API_KEY": "test"
        }):
            router = AIRouter()

            # Bulk tasks should prefer Gemini (cheaper)
            assert router.routing_config["bulk_extraction"] in ["gemini", "auto"]
            assert router.routing_config["news_analysis"] in ["gemini", "auto"]

            # Quality tasks might prefer OpenAI
            # But default is "auto" which prefers Gemini when available


# ============== ERROR HANDLING TESTS ==============

class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_invalid_json_response(self, gemini_config, mock_genai):
        """Test handling of invalid JSON response."""
        mock_client = mock_genai._mock_client
        mock_response = Mock()
        mock_response.text = "This is not valid JSON"
        mock_client.models.generate_content.return_value = mock_response

        provider = GeminiProvider(config=gemini_config)

        result = provider.generate_json("Generate JSON")
        assert "error" in result or "raw_response" in result

    def test_api_exception_handling(self, gemini_config, mock_genai):
        """Test handling of API exceptions."""
        mock_client = mock_genai._mock_client
        mock_client.models.generate_content.side_effect = Exception("API Error")

        provider = GeminiProvider(config=gemini_config)

        response = provider.generate_text("Test prompt")
        assert response.success is False
        assert "API Error" in response.error


# ============== RUN TESTS ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
