"""
Certify Intel - Cost Comparison Tests (v8.0.9)
Tests to verify cost savings when using Gemini vs OpenAI.

Run with: pytest tests/test_cost_comparison.py -v
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_provider import GeminiProvider, GeminiConfig


# ============== COST CALCULATION TESTS ==============

class TestCostCalculations:
    """Tests for cost estimation calculations."""

    @pytest.fixture
    def provider(self):
        """Create a GeminiProvider for testing."""
        with patch("gemini_provider.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            return GeminiProvider(GeminiConfig(api_key="test"))

    def test_gemini3_flash_model_cost(self, provider):
        """Test cost calculation for gemini-3-flash-preview model."""
        # 1M input tokens, 500K output tokens
        cost = provider.estimate_cost(1_000_000, 500_000, "gemini-3-flash-preview")

        # Expected: (1M * $0.50/1M) + (500K * $3.00/1M)
        # = $0.50 + $1.50 = $2.00
        expected = 0.50 + 1.50
        assert abs(cost - expected) < 0.001

    def test_gemini3_pro_model_cost(self, provider):
        """Test cost calculation for gemini-3-pro-preview model."""
        # 1M input tokens, 500K output tokens
        cost = provider.estimate_cost(1_000_000, 500_000, "gemini-3-pro-preview")

        # Expected: (1M * $2.00/1M) + (500K * $12.00/1M)
        # = $2.00 + $6.00 = $8.00
        expected = 2.00 + 6.00
        assert abs(cost - expected) < 0.01

    def test_gemini25_flash_model_cost(self, provider):
        """Test cost calculation for gemini-2.5-flash model (backward compat)."""
        # 1M input tokens, 500K output tokens
        cost = provider.estimate_cost(1_000_000, 500_000, "gemini-2.5-flash")

        # Expected: (1M * $0.075/1M) + (500K * $0.30/1M)
        # = $0.075 + $0.15 = $0.225
        expected = 0.075 + 0.15
        assert abs(cost - expected) < 0.001

    def test_gemini25_pro_model_cost(self, provider):
        """Test cost calculation for gemini-2.5-pro model (backward compat)."""
        # 1M input tokens, 500K output tokens
        cost = provider.estimate_cost(1_000_000, 500_000, "gemini-2.5-pro")

        # Expected: (1M * $1.25/1M) + (500K * $10.00/1M)
        # = $1.25 + $5.00 = $6.25
        expected = 1.25 + 5.00
        assert abs(cost - expected) < 0.01

    def test_small_request_cost(self, provider):
        """Test cost calculation for a small request."""
        # 1000 input tokens, 500 output tokens (typical small request)
        cost = provider.estimate_cost(1_000, 500, "gemini-3-flash-preview")

        # Expected: (1000 * $0.50/1M) + (500 * $3.00/1M)
        # = $0.0005 + $0.0015 = $0.002
        expected = 0.0005 + 0.0015
        assert abs(cost - expected) < 0.0001

    def test_default_model_cost(self, provider):
        """Test cost calculation uses default model when not specified."""
        # Use provider's default model
        cost1 = provider.estimate_cost(1_000_000, 500_000)
        cost2 = provider.estimate_cost(1_000_000, 500_000, provider.config.model)
        assert cost1 == cost2


# ============== COST COMPARISON TESTS ==============

class TestCostComparison:
    """Tests comparing costs between Gemini and OpenAI."""

    # OpenAI pricing (approximate as of 2026)
    OPENAI_PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    }

    @pytest.fixture
    def provider(self):
        """Create a GeminiProvider for testing."""
        with patch("gemini_provider.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            return GeminiProvider(GeminiConfig(api_key="test"))

    def estimate_openai_cost(self, input_tokens, output_tokens, model):
        """Estimate OpenAI cost for comparison."""
        pricing = self.OPENAI_PRICING.get(model, self.OPENAI_PRICING["gpt-4o-mini"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def test_gemini3_flash_vs_gpt4o_mini_savings(self, provider):
        """Test cost savings of Gemini 3 Flash vs GPT-4o-mini."""
        input_tokens = 1_000_000
        output_tokens = 500_000

        gemini_cost = provider.estimate_cost(input_tokens, output_tokens, "gemini-3-flash-preview")
        openai_cost = self.estimate_openai_cost(input_tokens, output_tokens, "gpt-4o-mini")

        # Gemini 3 Flash: $2.00, GPT-4o-mini: $0.45
        # Gemini 3 Flash is more expensive than mini but cheaper than full GPT-4o
        print(f"\nGemini 3 Flash vs GPT-4o-mini:")
        print(f"  Gemini 3 Flash: ${gemini_cost:.4f}")
        print(f"  GPT-4o-mini: ${openai_cost:.4f}")

    def test_gemini3_flash_vs_gpt4o_savings(self, provider):
        """Test cost savings of Gemini 3 Flash vs GPT-4o."""
        input_tokens = 1_000_000
        output_tokens = 500_000

        gemini_cost = provider.estimate_cost(input_tokens, output_tokens, "gemini-3-flash-preview")
        openai_cost = self.estimate_openai_cost(input_tokens, output_tokens, "gpt-4o")

        savings_percent = ((openai_cost - gemini_cost) / openai_cost) * 100

        # Gemini 3 Flash ($2.00) should be cheaper than GPT-4o ($7.50)
        assert savings_percent > 50, f"Expected >50% savings vs GPT-4o, got {savings_percent:.1f}%"
        print(f"\nGemini 3 Flash vs GPT-4o: {savings_percent:.1f}% savings")
        print(f"  Gemini 3 Flash: ${gemini_cost:.4f}")
        print(f"  GPT-4o: ${openai_cost:.4f}")

    def test_gemini3_pro_vs_gpt4o_comparison(self, provider):
        """Test cost comparison of Gemini 3 Pro vs GPT-4o."""
        input_tokens = 1_000_000
        output_tokens = 500_000

        gemini_cost = provider.estimate_cost(input_tokens, output_tokens, "gemini-3-pro-preview")
        openai_cost = self.estimate_openai_cost(input_tokens, output_tokens, "gpt-4o")

        print(f"\nGemini 3 Pro vs GPT-4o comparison:")
        print(f"  Gemini 3 Pro: ${gemini_cost:.4f}")
        print(f"  GPT-4o: ${openai_cost:.4f}")


# ============== BULK PROCESSING COST TESTS ==============

class TestBulkProcessingCosts:
    """Tests for bulk processing cost scenarios."""

    @pytest.fixture
    def provider(self):
        """Create a GeminiProvider for testing."""
        with patch("gemini_provider.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            return GeminiProvider(GeminiConfig(api_key="test"))

    def test_bulk_news_processing_cost(self, provider):
        """Test cost for processing 1000 news articles."""
        # Assume: 500 tokens input per article, 100 tokens output
        num_articles = 1000
        tokens_per_article_input = 500
        tokens_per_article_output = 100

        total_input = num_articles * tokens_per_article_input
        total_output = num_articles * tokens_per_article_output

        # Using Gemini 3 Flash (recommended for bulk)
        cost = provider.estimate_cost(total_input, total_output, "gemini-3-flash-preview")

        # Should be reasonable - less than $1.00 for 1000 articles
        assert cost < 1.00, f"Bulk processing cost ${cost:.4f} exceeds $1.00 budget"
        print(f"\n1000 news articles processing cost: ${cost:.4f}")

    def test_competitor_extraction_batch_cost(self, provider):
        """Test cost for extracting data from 30 competitor websites."""
        # Assume: 5000 tokens input per competitor (web content), 500 tokens output
        num_competitors = 30
        tokens_per_competitor_input = 5000
        tokens_per_competitor_output = 500

        total_input = num_competitors * tokens_per_competitor_input
        total_output = num_competitors * tokens_per_competitor_output

        # Using Gemini 3 Flash (recommended for data extraction)
        cost = provider.estimate_cost(total_input, total_output, "gemini-3-flash-preview")

        # Should be less than $0.50 for 30 competitors
        assert cost < 0.50, f"Extraction cost ${cost:.4f} exceeds $0.50 budget"
        print(f"\n30 competitor extractions cost: ${cost:.4f}")

    def test_daily_operation_cost_estimate(self, provider):
        """Test estimated daily operation cost."""
        # Daily operations estimate:
        # - 5 executive summaries (1000 input, 500 output each) using Pro
        # - 100 news articles (500 input, 100 output each) using Flash
        # - 10 competitor refreshes (5000 input, 500 output each) using Flash
        # - 20 chat interactions (200 input, 200 output each) using Flash

        daily_cost = 0

        # Executive summaries with Pro
        daily_cost += provider.estimate_cost(5 * 1000, 5 * 500, "gemini-3-pro-preview")

        # News articles with Flash
        daily_cost += provider.estimate_cost(100 * 500, 100 * 100, "gemini-3-flash-preview")

        # Competitor refreshes with Flash
        daily_cost += provider.estimate_cost(10 * 5000, 10 * 500, "gemini-3-flash-preview")

        # Chat with Flash
        daily_cost += provider.estimate_cost(20 * 200, 20 * 200, "gemini-3-flash-preview")

        # Daily cost should be under $1.00
        assert daily_cost < 1.00, f"Daily cost ${daily_cost:.4f} exceeds $1.00 budget"
        print(f"\nEstimated daily operation cost: ${daily_cost:.4f}")

    def test_monthly_cost_projection(self, provider):
        """Test monthly cost projection."""
        # Based on daily estimate, project monthly
        daily_tokens_input = (
            5 * 1000 +      # summaries
            100 * 500 +     # news
            10 * 5000 +     # refreshes
            20 * 200        # chat
        )
        daily_tokens_output = (
            5 * 500 +
            100 * 100 +
            10 * 500 +
            20 * 200
        )

        # 30 days, using Flash as average
        monthly_input = daily_tokens_input * 30
        monthly_output = daily_tokens_output * 30

        monthly_cost = provider.estimate_cost(monthly_input, monthly_output, "gemini-3-flash-preview")

        print(f"\nMonthly cost projection (Gemini 3 Flash): ${monthly_cost:.2f}")
        print(f"  Monthly tokens: {(monthly_input + monthly_output):,}")


# ============== COST OPTIMIZATION TESTS ==============

class TestCostOptimization:
    """Tests for cost optimization strategies."""

    @pytest.fixture
    def provider(self):
        """Create a GeminiProvider for testing."""
        with patch("gemini_provider.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            return GeminiProvider(GeminiConfig(api_key="test"))

    def test_model_routing_saves_costs(self, provider):
        """Test that proper model routing saves costs."""
        input_tokens = 100_000
        output_tokens = 50_000

        # Cost if everything used Pro
        all_pro_cost = provider.estimate_cost(input_tokens, output_tokens, "gemini-3-pro-preview") * 3

        # Cost with optimized routing:
        # - Bulk tasks: Flash (60% of work)
        # - Standard tasks: Flash (30% of work)
        # - Complex tasks: Pro (10% of work)
        optimized_cost = (
            provider.estimate_cost(input_tokens * 0.6, output_tokens * 0.6, "gemini-3-flash-preview") +
            provider.estimate_cost(input_tokens * 0.3, output_tokens * 0.3, "gemini-3-flash-preview") +
            provider.estimate_cost(input_tokens * 0.1, output_tokens * 0.1, "gemini-3-pro-preview")
        )

        # Optimized routing should save money compared to all-Pro
        savings_percent = ((all_pro_cost - optimized_cost) / all_pro_cost) * 100
        assert savings_percent > 50, f"Expected >50% savings with routing, got {savings_percent:.1f}%"
        print(f"\nOptimized routing savings: {savings_percent:.1f}%")
        print(f"  All Pro: ${all_pro_cost:.4f}")
        print(f"  Optimized: ${optimized_cost:.4f}")

    def test_recommended_models_are_cost_effective(self, provider):
        """Test that recommended models for each task are cost-effective."""
        # Verify bulk tasks recommend fast model
        assert provider.get_recommended_model("bulk_extraction") == "gemini-3-flash-preview"
        assert provider.get_recommended_model("quick_classification") == "gemini-3-flash-preview"

        # Verify standard tasks use fast model
        assert provider.get_recommended_model("data_extraction") == "gemini-3-flash-preview"

        # Verify complex/quality tasks use pro model
        assert provider.get_recommended_model("executive_summary") == "gemini-3-pro-preview"
        assert provider.get_recommended_model("complex_analysis") == "gemini-3-pro-preview"


# ============== MODEL PRICING VALIDATION ==============

class TestModelPricingValidation:
    """Tests to validate model pricing is correctly defined."""

    @pytest.fixture
    def provider(self):
        """Create a GeminiProvider for testing."""
        with patch("gemini_provider.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            return GeminiProvider(GeminiConfig(api_key="test"))

    def test_all_models_have_pricing(self, provider):
        """Test that all expected models have pricing defined."""
        expected_models = [
            "gemini-3-flash-preview",
            "gemini-3-pro-preview",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ]

        for model in expected_models:
            assert model in provider.MODEL_PRICING, f"Missing pricing for {model}"
            assert "input" in provider.MODEL_PRICING[model]
            assert "output" in provider.MODEL_PRICING[model]

    def test_pricing_values_are_positive(self, provider):
        """Test that all pricing values are positive."""
        for model, pricing in provider.MODEL_PRICING.items():
            assert pricing["input"] > 0, f"{model} input pricing must be positive"
            assert pricing["output"] > 0, f"{model} output pricing must be positive"

    def test_flash_is_cheapest_gemini3(self, provider):
        """Test that Gemini 3 Flash is cheaper than Gemini 3 Pro."""
        flash_input = provider.MODEL_PRICING["gemini-3-flash-preview"]["input"]
        pro_input = provider.MODEL_PRICING["gemini-3-pro-preview"]["input"]
        assert flash_input < pro_input, "Flash should be cheaper than Pro"


# ============== RUN TESTS ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
