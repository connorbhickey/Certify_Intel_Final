"""
Certify Intel - AI Evaluator Tests

Tests for the Opik-based AI response evaluation module.

Run: python -m pytest -xvs tests/test_ai_evaluator.py
"""

import pytest
from unittest.mock import patch


class TestAIEvaluatorConfig:
    """Test AI evaluator configuration and defaults."""

    def test_disabled_by_default(self, monkeypatch):
        """Evaluator should be disabled when OPIK_ENABLED is not set."""
        monkeypatch.delenv("OPIK_ENABLED", raising=False)
        import importlib
        import ai_evaluator
        importlib.reload(ai_evaluator)
        assert ai_evaluator.OPIK_ENABLED is False

    def test_evaluator_singleton(self):
        """get_evaluator() should return the same instance."""
        import ai_evaluator
        ai_evaluator._evaluator = None  # Reset singleton
        e1 = ai_evaluator.get_evaluator()
        e2 = ai_evaluator.get_evaluator()
        assert e1 is e2
        ai_evaluator._evaluator = None  # Cleanup


class TestEvalResult:
    """Test the EvalResult dataclass."""

    def test_default_scores(self):
        """EvalResult should have correct defaults."""
        from ai_evaluator import EvalResult
        result = EvalResult()
        assert result.hallucination_score == 0.0
        assert result.groundedness_score == 1.0
        assert result.relevance_score == 1.0
        assert result.coherence_score == 1.0

    def test_overall_score_calculation(self):
        """overall_score should be weighted average of component scores."""
        from ai_evaluator import EvalResult
        result = EvalResult(
            hallucination_score=0.0,
            groundedness_score=1.0,
            relevance_score=1.0,
            coherence_score=1.0,
        )
        # (1-0)*0.3 + 1.0*0.3 + 1.0*0.2 + 1.0*0.2 = 0.3+0.3+0.2+0.2 = 1.0
        assert result.overall_score == 1.0

    def test_overall_score_with_hallucination(self):
        """overall_score should decrease with hallucination."""
        from ai_evaluator import EvalResult
        result = EvalResult(
            hallucination_score=1.0,
            groundedness_score=0.0,
            relevance_score=1.0,
            coherence_score=1.0,
        )
        # (1-1)*0.3 + 0.0*0.3 + 1.0*0.2 + 1.0*0.2 = 0+0+0.2+0.2 = 0.4
        assert result.overall_score == pytest.approx(0.4)

    def test_to_dict_keys(self):
        """to_dict() should return expected keys with rounded values."""
        from ai_evaluator import EvalResult
        result = EvalResult()
        d = result.to_dict()
        expected_keys = {
            "hallucination_score",
            "groundedness_score",
            "relevance_score",
            "coherence_score",
            "overall_score",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_values_are_rounded(self):
        """to_dict() values should be rounded to 3 decimal places."""
        from ai_evaluator import EvalResult
        result = EvalResult(
            hallucination_score=0.12345,
            groundedness_score=0.87654,
        )
        d = result.to_dict()
        assert d["hallucination_score"] == 0.123
        assert d["groundedness_score"] == 0.877

    def test_details_defaults_to_empty_dict(self):
        """details should default to empty dict, not None."""
        from ai_evaluator import EvalResult
        result = EvalResult()
        assert result.details == {}


class TestAIEvaluatorClass:
    """Test AIEvaluator class methods."""

    @pytest.mark.asyncio
    async def test_evaluate_returns_perfect_scores_when_disabled(self):
        """evaluate_response() should return perfect scores when disabled."""
        from ai_evaluator import AIEvaluator
        evaluator = AIEvaluator()
        evaluator.is_available = False

        result = await evaluator.evaluate_response(
            query="What is Epic's pricing?",
            response="Epic charges $500/month.",
            context="Epic pricing is $500/month.",
        )

        assert result.hallucination_score == 0.0
        assert result.overall_score == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_handles_opik_import_error(self):
        """evaluate_response() should handle missing opik gracefully."""
        from ai_evaluator import AIEvaluator
        evaluator = AIEvaluator()
        evaluator.is_available = True

        with patch.dict("sys.modules", {"opik": None}):
            evaluator._opik_client = None
            result = await evaluator.evaluate_response(
                query="test", response="test"
            )

        # Should return perfect scores on failure
        assert result.hallucination_score == 0.0
        assert result.overall_score == 1.0

    def test_evaluator_is_available_false_when_disabled(self, monkeypatch):
        """AIEvaluator.is_available should be False when OPIK_ENABLED=false."""
        monkeypatch.setenv("OPIK_ENABLED", "false")
        import importlib
        import ai_evaluator
        importlib.reload(ai_evaluator)
        evaluator = ai_evaluator.AIEvaluator()
        assert evaluator.is_available is False

    def test_evaluator_opik_client_starts_none(self):
        """AIEvaluator should start with _opik_client=None (lazy init)."""
        from ai_evaluator import AIEvaluator
        evaluator = AIEvaluator()
        assert evaluator._opik_client is None

    @pytest.mark.asyncio
    async def test_evaluate_returns_eval_result_type(self):
        """evaluate_response() should always return an EvalResult."""
        from ai_evaluator import AIEvaluator, EvalResult
        evaluator = AIEvaluator()
        evaluator.is_available = False
        result = await evaluator.evaluate_response(
            query="test query",
            response="test response"
        )
        assert isinstance(result, EvalResult)

    def test_overall_score_partial_hallucination(self):
        """overall_score with partial hallucination should be between 0 and 1."""
        from ai_evaluator import EvalResult
        result = EvalResult(
            hallucination_score=0.5,
            groundedness_score=0.5,
            relevance_score=0.5,
            coherence_score=0.5,
        )
        # (1-0.5)*0.3 + 0.5*0.3 + 0.5*0.2 + 0.5*0.2 = 0.15+0.15+0.1+0.1 = 0.5
        assert result.overall_score == pytest.approx(0.5)
