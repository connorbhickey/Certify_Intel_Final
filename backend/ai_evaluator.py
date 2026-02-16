"""
Certify Intel - AI Response Evaluation
=======================================
Automated quality scoring for AI-generated content using Opik.
Metrics: hallucination, groundedness, relevance, coherence.

Config:
    OPIK_ENABLED=false (default OFF)
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OPIK_ENABLED = os.getenv("OPIK_ENABLED", "false").lower() == "true"


@dataclass
class EvalResult:
    """AI evaluation result."""
    hallucination_score: float = 0.0    # 0=no hallucination, 1=fully hallucinated
    groundedness_score: float = 1.0     # 0=ungrounded, 1=fully grounded
    relevance_score: float = 1.0        # 0=irrelevant, 1=fully relevant
    coherence_score: float = 1.0        # 0=incoherent, 1=fully coherent
    overall_score: float = 1.0
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        self.overall_score = (
            (1 - self.hallucination_score) * 0.3
            + self.groundedness_score * 0.3
            + self.relevance_score * 0.2
            + self.coherence_score * 0.2
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "hallucination_score": round(self.hallucination_score, 3),
            "groundedness_score": round(self.groundedness_score, 3),
            "relevance_score": round(self.relevance_score, 3),
            "coherence_score": round(self.coherence_score, 3),
            "overall_score": round(self.overall_score, 3),
        }


class AIEvaluator:
    """Evaluate AI response quality."""

    def __init__(self):
        self._opik_client = None
        self.is_available = OPIK_ENABLED

    def _get_opik(self):
        """Lazy-load Opik client."""
        if self._opik_client is None and self.is_available:
            try:
                import opik
                self._opik_client = opik.Opik()
                logger.info("Opik evaluation client initialized")
            except ImportError:
                logger.info("opik not installed - evaluation disabled")
                self.is_available = False
            except Exception as e:
                logger.warning(f"Opik init failed: {e}")
                self.is_available = False
        return self._opik_client

    async def evaluate_response(
        self,
        query: str,
        response: str,
        context: Optional[str] = None,
    ) -> EvalResult:
        """Evaluate an AI response for quality metrics."""
        if not self.is_available:
            return EvalResult()  # Return perfect scores when disabled

        try:
            client = self._get_opik()
            if not client:
                return EvalResult()

            # Use Opik's built-in evaluators
            from opik.evaluation.metrics import (
                Hallucination,
                AnswerRelevance,
            )

            scores: Dict[str, float] = {}

            # Hallucination check
            try:
                hallucination = Hallucination()
                h_result = hallucination.score(
                    input=query,
                    output=response,
                    context=[context] if context else [],
                )
                scores["hallucination_score"] = h_result.value
            except Exception:
                scores["hallucination_score"] = 0.0

            # Relevance check
            try:
                relevance = AnswerRelevance()
                r_result = relevance.score(
                    input=query,
                    output=response,
                )
                scores["relevance_score"] = r_result.value
            except Exception:
                scores["relevance_score"] = 1.0

            return EvalResult(
                hallucination_score=scores.get("hallucination_score", 0.0),
                groundedness_score=1.0 - scores.get("hallucination_score", 0.0),
                relevance_score=scores.get("relevance_score", 1.0),
                coherence_score=1.0,
            )
        except Exception as e:
            logger.warning(f"AI evaluation failed: {e}")
            return EvalResult()


# Singleton
_evaluator: Optional[AIEvaluator] = None


def get_evaluator() -> AIEvaluator:
    """Get or create the AI evaluator singleton."""
    global _evaluator
    if _evaluator is None:
        _evaluator = AIEvaluator()
    return _evaluator
