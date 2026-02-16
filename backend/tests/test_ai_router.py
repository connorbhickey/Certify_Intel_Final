"""
Certify Intel v7.0 - AI Router Tests
=====================================

Tests for the multi-model AI routing system.

Coverage:
- Model selection based on task type
- Cost estimation accuracy
- Budget enforcement
- Fallback behavior

Run:
    pytest tests/test_ai_router.py -v
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# TEST: Model Configuration
# =============================================================================

class TestModelConfiguration:
    """Test model configuration and registry."""

    def test_models_have_required_fields(self):
        """All models should have required configuration fields."""
        try:
            from ai_router import MODELS, ModelConfig
        except ImportError:
            pytest.skip("AI Router not available")

        for name, config in MODELS.items():
            assert hasattr(config, 'name'), f"{name} missing 'name'"
            assert hasattr(config, 'provider'), f"{name} missing 'provider'"
            assert hasattr(config, 'input_cost_per_1m'), f"{name} missing 'input_cost_per_1m'"
            assert hasattr(config, 'output_cost_per_1m'), f"{name} missing 'output_cost_per_1m'"
            assert hasattr(config, 'context_window'), f"{name} missing 'context_window'"
            assert hasattr(config, 'best_for'), f"{name} missing 'best_for'"

    def test_all_task_types_have_default_model(self):
        """Every task type should have a default model assigned."""
        try:
            from ai_router import TaskType, TASK_TO_DEFAULT_MODEL
        except ImportError:
            pytest.skip("AI Router not available")

        for task_type in TaskType:
            assert task_type in TASK_TO_DEFAULT_MODEL, \
                f"TaskType.{task_type.name} has no default model"

    def test_gemini_is_cheapest_for_general_tasks(self):
        """Gemini Flash should be cheapest for general/chat tasks."""
        try:
            from ai_router import MODELS, TaskType
        except ImportError:
            pytest.skip("AI Router not available")

        # Find models suitable for chat
        chat_models = [
            (name, config) for name, config in MODELS.items()
            if TaskType.CHAT in config.best_for
        ]

        # Sort by input cost
        chat_models.sort(key=lambda x: x[1].input_cost_per_1m)

        # Gemini should be among the cheapest
        assert chat_models[0][0] in ["gemini-3-flash-preview", "gpt-4o-mini"]


# =============================================================================
# TEST: Cost Estimation
# =============================================================================

class TestCostEstimation:
    """Test cost estimation accuracy."""

    def test_cost_calculation_accuracy(self):
        """Cost calculation should match expected values."""
        try:
            from ai_router import AIRouter
        except ImportError:
            pytest.skip("AI Router not available")

        router = AIRouter()

        # Gemini 3 Flash: $0.50 input, $3.00 output per 1M tokens
        cost = router.estimate_cost(
            model="gemini-3-flash-preview",
            prompt_tokens=1_000_000,
            expected_output_tokens=1_000_000
        )
        expected = 0.50 + 3.00  # = $3.50
        assert abs(cost - expected) < 0.001, f"Expected {expected}, got {cost}"

    def test_cost_scales_with_tokens(self):
        """Cost should scale linearly with token count."""
        try:
            from ai_router import AIRouter
        except ImportError:
            pytest.skip("AI Router not available")

        router = AIRouter()

        cost_1x = router.estimate_cost("gemini-3-flash-preview", 100000, 10000)
        cost_2x = router.estimate_cost("gemini-3-flash-preview", 200000, 20000)

        assert abs(cost_2x - (cost_1x * 2)) < 0.0001, "Cost should double with 2x tokens"

    def test_opus_is_most_expensive(self):
        """Claude Opus should be the most expensive model."""
        try:
            from ai_router import MODELS
        except ImportError:
            pytest.skip("AI Router not available")

        opus_cost = MODELS["claude-opus-4.5"].input_cost_per_1m
        for name, config in MODELS.items():
            if name != "claude-opus-4.5":
                assert config.input_cost_per_1m <= opus_cost, \
                    f"{name} is more expensive than Opus"


# =============================================================================
# TEST: Task Routing
# =============================================================================

class TestTaskRouting:
    """Test model selection based on task type."""

    @pytest.mark.asyncio
    async def test_bulk_extraction_routes_to_cheap_model(self):
        """Bulk extraction should route to a cheap model."""
        try:
            from ai_router import AIRouter, TaskType, MODELS
        except ImportError:
            pytest.skip("AI Router not available")

        router = AIRouter()

        model = await router.route_request(
            task_type=TaskType.BULK_EXTRACTION,
            prompt_tokens=500000,
            expected_output_tokens=100000
        )

        # Should be a cheap model (not Opus or Sonnet)
        assert MODELS[model].input_cost_per_1m < 5.0, \
            f"Bulk extraction routed to expensive model: {model}"

    @pytest.mark.asyncio
    async def test_strategy_routes_to_premium_model(self):
        """Strategic decisions should route to a premium model."""
        try:
            from ai_router import AIRouter, TaskType
        except ImportError:
            pytest.skip("AI Router not available")

        router = AIRouter()

        model = await router.route_request(
            task_type=TaskType.STRATEGY,
            prompt_tokens=5000,
            expected_output_tokens=3000
        )

        # Should be Claude Opus for strategy
        assert model == "claude-opus-4.5", f"Strategy routed to: {model}"

    @pytest.mark.asyncio
    async def test_respects_max_cost_constraint(self):
        """Router should respect max_cost_usd constraint."""
        try:
            from ai_router import AIRouter, TaskType
        except ImportError:
            pytest.skip("AI Router not available")

        router = AIRouter()

        # Request with very low budget
        model = await router.route_request(
            task_type=TaskType.STRATEGY,
            prompt_tokens=10000,
            expected_output_tokens=5000,
            max_cost_usd=0.001  # Very low budget
        )

        # Should fall back to cheapest model
        assert model in ["gemini-3-flash-preview", "gpt-4o-mini"]


# =============================================================================
# TEST: Budget Enforcement
# =============================================================================

class TestBudgetEnforcement:
    """Test daily budget enforcement."""

    def test_budget_starts_at_zero(self):
        """New tracker should have zero spend."""
        try:
            from ai_router import CostTracker
        except ImportError:
            pytest.skip("AI Router not available")

        tracker = CostTracker(daily_budget_usd=50.0)
        assert tracker.get_today_spend() == 0.0

    def test_remaining_budget_calculation(self):
        """Remaining budget should be accurate."""
        try:
            from ai_router import CostTracker, TaskType
        except ImportError:
            pytest.skip("AI Router not available")

        tracker = CostTracker(daily_budget_usd=50.0)

        # Record some usage
        tracker.record_usage(
            model="gemini-3-flash-preview",
            task_type=TaskType.CHAT,
            tokens_input=1_000_000,
            tokens_output=100_000
        )

        spent = tracker.get_today_spend()
        remaining = tracker.get_remaining_budget()

        assert spent + remaining == 50.0

    def test_budget_check_works(self):
        """Budget check should work correctly."""
        try:
            from ai_router import CostTracker
        except ImportError:
            pytest.skip("AI Router not available")

        tracker = CostTracker(daily_budget_usd=10.0)

        # Should allow small request
        assert tracker.check_budget(estimated_cost=5.0) == True

        # Should block large request
        assert tracker.check_budget(estimated_cost=15.0) == False

    def test_usage_summary(self):
        """Usage summary should aggregate correctly."""
        try:
            from ai_router import CostTracker, TaskType
        except ImportError:
            pytest.skip("AI Router not available")

        tracker = CostTracker(daily_budget_usd=50.0)

        # Record multiple usages
        for i in range(5):
            tracker.record_usage(
                model="gemini-3-flash-preview",
                task_type=TaskType.CHAT,
                tokens_input=10000,
                tokens_output=5000
            )

        summary = tracker.get_usage_summary()

        assert summary["total_requests"] == 5
        assert summary["total_tokens_input"] == 50000
        assert summary["total_tokens_output"] == 25000
        assert "by_model" in summary
        assert "gemini-3-flash-preview" in summary["by_model"]


# =============================================================================
# TEST: Cost Savings Calculation
# =============================================================================

class TestCostSavings:
    """Test that optimized routing actually saves money."""

    def test_bulk_task_savings(self):
        """Verify savings on bulk extraction tasks."""
        try:
            from ai_router import AIRouter, MODELS
        except ImportError:
            pytest.skip("AI Router not available")

        router = AIRouter()

        # 500K input, 100K output (typical bulk extraction)
        input_tokens = 500_000
        output_tokens = 100_000

        # Cost with premium model (original plan)
        opus_cost = router.estimate_cost("claude-opus-4.5", input_tokens, output_tokens)

        # Cost with optimized routing (Gemini Flash)
        flash_cost = router.estimate_cost("gemini-3-flash-preview", input_tokens, output_tokens)

        savings = (opus_cost - flash_cost) / opus_cost * 100

        assert savings > 90, f"Expected >90% savings, got {savings:.1f}%"

    def test_daily_cost_comparison(self):
        """Compare daily costs between plans."""
        try:
            from ai_router import AIRouter
        except ImportError:
            pytest.skip("AI Router not available")

        router = AIRouter()

        # Simulate daily usage:
        # - 100 competitor discoveries (500K input, 200K output each)
        # - 10 battlecards (50K input, 30K output each)
        # - 1000 chat queries (1K input, 500 output each)

        # Original plan (all Claude Opus)
        original_cost = (
            router.estimate_cost("claude-opus-4.5", 500000, 200000) +  # Discovery
            10 * router.estimate_cost("claude-opus-4.5", 50000, 30000) +  # Battlecards
            1000 * router.estimate_cost("claude-opus-4.5", 1000, 500)  # Chat
        )

        # Optimized plan (task-based routing)
        optimized_cost = (
            router.estimate_cost("gemini-3-flash-preview", 500000, 200000) +  # Discovery
            10 * router.estimate_cost("gemini-3-flash-preview", 50000, 30000) +  # Battlecards
            1000 * router.estimate_cost("gemini-3-flash-preview", 1000, 500)  # Chat
        )

        savings_pct = (original_cost - optimized_cost) / original_cost * 100

        print(f"\nDaily Cost Comparison:")
        print(f"  Original (Claude Opus): ${original_cost:.2f}")
        print(f"  Optimized (Gemini Flash): ${optimized_cost:.2f}")
        print(f"  Savings: {savings_pct:.1f}%")

        assert savings_pct > 80, f"Expected >80% savings, got {savings_pct:.1f}%"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
