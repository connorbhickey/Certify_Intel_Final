"""
Certify Intel - AI Dimension Analyzer (v5.1.0)
AI-powered dimension classification and scoring.

Analyzes news articles, customer reviews, and competitor data to:
- Classify content by relevant competitive dimension
- Infer dimension scores from review sentiment
- Generate evidence summaries from multiple sources
- Suggest dimension scores based on all available data

Supports prompt_key for user-customizable AI prompts via SystemPrompt table.
Uses the existing OpenAI/Gemini hybrid AI infrastructure.
"""

from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import json
import os
import logging

from sales_marketing_module import (
    DimensionID,
    DIMENSION_METADATA,
    SCORE_LABELS,
    calculate_dimension_match
)

logger = logging.getLogger(__name__)

NO_HALLUCINATION_INSTRUCTION = (
    "\n\nCRITICAL DATA INTEGRITY RULE: You must ONLY reference data provided "
    "in this context. Do NOT fabricate, estimate, or assume any data points. "
    "If data is not available, state 'No verified data available for this metric.'"
)


class DimensionAnalyzer:
    """
    Analyzes text content to classify by dimension and infer scores.
    Uses existing OpenAI/Gemini integration from gemini_provider.py.
    """

    def __init__(self):
        """Initialize the analyzer with AI provider configuration."""
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.gemini_key = os.getenv("GOOGLE_AI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1")
        self.ai_provider = os.getenv("AI_PROVIDER", "openai")

    @staticmethod
    def _resolve_prompt(db, user_id: Optional[int], prompt_key: Optional[str], default: str) -> str:
        """Resolve a system prompt by key with user-specific override, or return default."""
        if not prompt_key or not db:
            return default
        try:
            from database import SystemPrompt
            # User-specific override first
            p = db.query(SystemPrompt).filter(
                SystemPrompt.key == prompt_key,
                SystemPrompt.user_id == user_id
            ).first()
            if not p:
                # Global fallback
                p = db.query(SystemPrompt).filter(
                    SystemPrompt.key == prompt_key,
                    SystemPrompt.user_id == None  # noqa: E711
                ).first()
            return p.content if p else default
        except Exception as e:
            logger.warning(f"Failed to resolve prompt_key '{prompt_key}': {e}")
            return default

    def _get_ai_client(self):
        """Get the appropriate AI client based on configuration."""
        if self.ai_provider == "gemini" and self.gemini_key:
            try:
                from gemini_provider import GeminiProvider
                return GeminiProvider()
            except ImportError:
                pass

        if self.openai_key:
            try:
                from openai import OpenAI
                return OpenAI(api_key=self.openai_key)
            except ImportError:
                pass

        return None

    def classify_article_dimension(
        self,
        title: str,
        snippet: str,
        competitor_name: str,
        prompt_key: Optional[str] = None,
        db=None,
        user_id: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        Classify which dimensions a news article relates to.

        Args:
            title: Article title
            snippet: Article snippet/summary
            competitor_name: Name of the competitor
            prompt_key: Optional prompt key for user-customizable prompts
            db: Optional database session for prompt resolution
            user_id: Optional user ID for user-specific prompt overrides

        Returns:
            List of (dimension_id, confidence) tuples sorted by confidence
        """
        # First try keyword-based matching (fast, no API call)
        text = f"{title} {snippet}".lower()
        keyword_matches = []

        for dim_id in DimensionID:
            is_match, confidence = calculate_dimension_match(text, dim_id.value)
            if is_match:
                keyword_matches.append((dim_id.value, confidence))

        # If we have good keyword matches, return them
        if keyword_matches and max(c for _, c in keyword_matches) > 0.5:
            return sorted(keyword_matches, key=lambda x: x[1], reverse=True)

        # Otherwise, use AI for classification
        client = self._get_ai_client()
        if not client:
            logger.warning("No AI client available for dimension classification")
            return keyword_matches

        try:
            default_prompt = self._build_classification_prompt(title, snippet, competitor_name)
            prompt = self._resolve_prompt(
                db, user_id, prompt_key or "dimension_classification", default_prompt
            ) + NO_HALLUCINATION_INSTRUCTION

            if hasattr(client, 'generate_json'):
                # Gemini provider
                response = client.generate_json(prompt)
                if response.success:
                    return self._parse_classification_response(response.content)
            else:
                # OpenAI client
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                content = response.choices[0].message.content
                return self._parse_classification_response(json.loads(content))

        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return keyword_matches

        return keyword_matches

    def _build_classification_prompt(
        self,
        title: str,
        snippet: str,
        competitor_name: str
    ) -> str:
        """Build the prompt for dimension classification."""
        dimensions_desc = "\n".join([
            f"- {dim_id.value}: {meta['name']} - {meta['description']}"
            for dim_id, meta in DIMENSION_METADATA.items()
        ])

        return f"""Analyze this news article about {competitor_name} and classify which competitive dimensions it relates to.

Article Title: {title}
Article Snippet: {snippet}

Available Dimensions:
{dimensions_desc}

Return a JSON object with the following structure:
{{
    "dimensions": [
        {{"dimension_id": "dimension_name", "confidence": 0.0-1.0, "reason": "brief explanation"}}
    ]
}}

Only include dimensions with confidence > 0.3. Return empty array if no dimensions match."""

    def _parse_classification_response(self, response: Any) -> List[Tuple[str, float]]:
        """Parse AI classification response."""
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                return []

        dimensions = response.get("dimensions", [])
        return [
            (d["dimension_id"], d["confidence"])
            for d in dimensions
            if d.get("dimension_id") and d.get("confidence", 0) > 0.3
        ]

    def analyze_review_dimensions(
        self,
        review_text: str,
        review_rating: float,
        competitor_name: str
    ) -> Dict[str, int]:
        """
        Extract dimension signals from a customer review.

        Args:
            review_text: The full review text
            review_rating: Star rating (1-5)
            competitor_name: Name of the competitor

        Returns:
            Dict of dimension_id -> inferred score (1-5)
        """
        # Keyword-based quick analysis
        dimension_signals = {}
        text_lower = review_text.lower()

        for dim_id in DimensionID:
            meta = DIMENSION_METADATA[dim_id]
            positive_signals = 0
            negative_signals = 0

            # Check for review signals
            for signal in meta.get("review_signals", []):
                if signal.lower() in text_lower:
                    # Determine if the context is positive or negative
                    # This is a simplified heuristic
                    signal_idx = text_lower.find(signal.lower())
                    context = text_lower[max(0, signal_idx-50):signal_idx+50]

                    negative_words = ["not", "no", "poor", "bad", "slow", "difficult", "hard", "issue", "problem"]
                    positive_words = ["great", "good", "excellent", "easy", "fast", "helpful", "love", "amazing"]

                    has_negative = any(nw in context for nw in negative_words)
                    has_positive = any(pw in context for pw in positive_words)

                    if has_negative and not has_positive:
                        negative_signals += 1
                    elif has_positive and not has_negative:
                        positive_signals += 1

            # Calculate inferred score for this dimension
            if positive_signals > 0 or negative_signals > 0:
                # Base score influenced by overall rating
                base_score = round(review_rating)

                # Adjust based on specific signals
                signal_adjustment = (positive_signals - negative_signals) * 0.5
                inferred_score = base_score + signal_adjustment

                # Clamp to 1-5
                inferred_score = max(1, min(5, round(inferred_score)))
                dimension_signals[dim_id.value] = inferred_score

        # If no signals found but we have a rating, skip
        if not dimension_signals:
            return {}

        return dimension_signals

    def generate_dimension_evidence(
        self,
        competitor_name: str,
        dimension_id: str,
        sources: List[Dict]
    ) -> str:
        """
        Generate evidence summary for a dimension from multiple sources.

        Args:
            competitor_name: Name of the competitor
            dimension_id: The dimension to summarize
            sources: List of source dicts with 'type', 'content', 'date'

        Returns:
            Summarized evidence text
        """
        meta = DIMENSION_METADATA.get(DimensionID(dimension_id))
        if not meta:
            return ""

        if not sources:
            return f"No evidence collected for {meta['name']}."

        client = self._get_ai_client()
        if not client:
            # Fallback to simple concatenation
            evidence_parts = []
            for source in sources[:5]:
                source_type = source.get("type", "Unknown")
                content = source.get("content", "")[:200]
                evidence_parts.append(f"[{source_type}] {content}")
            return "\n".join(evidence_parts)

        try:
            sources_text = "\n\n".join([
                f"Source ({s.get('type', 'unknown')}, {s.get('date', 'unknown date')}):\n{s.get('content', '')[:500]}"
                for s in sources[:10]
            ])

            prompt = f"""Summarize the evidence about {competitor_name}'s {meta['name']} dimension.

Dimension: {meta['name']}
Description: {meta['description']}
Deal Impact: {meta['deal_impact']}

Sources:
{sources_text}

Write a concise 2-3 sentence evidence summary that:
1. Captures the key facts about this dimension
2. Notes any specific data points or quotes
3. Indicates the overall assessment (strong/weak/neutral)

Keep it factual and cite specific sources where possible.""" + NO_HALLUCINATION_INSTRUCTION

            if hasattr(client, 'generate_text'):
                response = client.generate_text(prompt)
                if response.success:
                    return response.content
            else:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=300
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Failed to generate evidence: {e}")
            return f"Evidence from {len(sources)} sources. AI summary unavailable."

        return ""

    def suggest_dimension_scores(
        self,
        competitor_id: int,
        competitor_name: str,
        db_session,
        prompt_key: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Dict]:
        """
        AI-suggested dimension scores based on all available data.

        Args:
            competitor_id: Database ID of the competitor
            competitor_name: Name of the competitor
            db_session: Database session
            prompt_key: Optional prompt key for user-customizable prompts
            user_id: Optional user ID for user-specific prompt overrides

        Returns:
            Dict with score, evidence, confidence for each dimension
        """
        from database import Competitor, DataSource, DimensionNewsTag

        # Gather all available data
        competitor = db_session.query(Competitor).filter(
            Competitor.id == competitor_id
        ).first()

        if not competitor:
            return {}

        # Collect data sources
        data_sources = db_session.query(DataSource).filter(
            DataSource.competitor_id == competitor_id
        ).all()

        # Collect news tags
        news_tags = db_session.query(DimensionNewsTag).filter(
            DimensionNewsTag.competitor_id == competitor_id
        ).all()

        # Build context for AI
        context_parts = []

        # Basic company info
        context_parts.append(f"Competitor: {competitor.name}")
        context_parts.append(f"Website: {competitor.website or 'Unknown'}")
        context_parts.append(f"Threat Level: {competitor.threat_level}")

        # Existing data points
        for ds in data_sources[:20]:
            if ds.current_value:
                context_parts.append(f"{ds.field_name}: {ds.current_value}")

        # Product info
        if competitor.key_features:
            context_parts.append(f"Key Features: {competitor.key_features}")
        if competitor.pricing_model:
            context_parts.append(f"Pricing Model: {competitor.pricing_model}")
        if competitor.ehr_integrations:
            context_parts.append(f"EHR Integrations: {competitor.ehr_integrations}")

        context_text = "\n".join(context_parts)

        client = self._get_ai_client()
        if not client:
            logger.warning("No AI client available for dimension suggestions")
            return self._fallback_dimension_suggestions(competitor)

        try:
            default_prompt = self._build_suggestion_prompt(competitor_name, context_text)
            prompt = self._resolve_prompt(
                db_session, user_id, prompt_key or "dimension_scoring", default_prompt
            ) + NO_HALLUCINATION_INSTRUCTION

            if hasattr(client, 'generate_json'):
                response = client.generate_json(prompt)
                if response.success:
                    return self._parse_suggestion_response(response.content)
            else:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.4
                )
                content = response.choices[0].message.content
                return self._parse_suggestion_response(json.loads(content))

        except Exception as e:
            logger.error(f"AI suggestion failed: {e}")
            return self._fallback_dimension_suggestions(competitor)

        return {}

    def _build_suggestion_prompt(self, competitor_name: str, context: str) -> str:
        """Build prompt for dimension score suggestions."""
        dimensions_desc = "\n".join([
            f"- {dim_id.value}: {meta['name']}\n  Score Guide: {json.dumps(meta['score_guide'])}"
            for dim_id, meta in DIMENSION_METADATA.items()
        ])

        return f"""Based on the available data about {competitor_name}, suggest scores (1-5) for each competitive dimension.

Available Data:
{context}

Dimensions and Scoring Guides:
{dimensions_desc}

Return a JSON object:
{{
    "suggestions": {{
        "dimension_id": {{
            "score": 1-5,
            "evidence": "Brief explanation based on available data",
            "confidence": "low|medium|high"
        }}
    }}
}}

Only include dimensions where you have some data to support a score.
Use "low" confidence if extrapolating from limited data.
Use "medium" confidence if you have some direct evidence.
Use "high" confidence only if multiple data points support the score."""

    def _parse_suggestion_response(self, response: Any) -> Dict[str, Dict]:
        """Parse AI suggestion response."""
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                return {}

        return response.get("suggestions", {})

    def _fallback_dimension_suggestions(self, competitor) -> Dict[str, Dict]:
        """Generate basic suggestions without AI based on available fields."""
        suggestions = {}

        # Integration depth based on EHR integrations
        if competitor.ehr_integrations:
            integration_count = len(competitor.ehr_integrations.split(";"))
            score = min(5, 2 + integration_count)
            suggestions["integration_depth"] = {
                "score": score,
                "evidence": f"Has {integration_count} EHR integrations: {competitor.ehr_integrations}",
                "confidence": "low"
            }

        # Pricing flexibility based on pricing model
        if competitor.pricing_model:
            model = competitor.pricing_model.lower()
            if "custom" in model or "flexible" in model:
                score = 4
            elif "subscription" in model or "per" in model:
                score = 3
            else:
                score = 2
            suggestions["pricing_flexibility"] = {
                "score": score,
                "evidence": f"Pricing model: {competitor.pricing_model}",
                "confidence": "low"
            }

        # Reliability based on public company status
        if competitor.is_public:
            suggestions["reliability_enterprise"] = {
                "score": 4,
                "evidence": f"Public company ({competitor.ticker_symbol}) with enterprise customers",
                "confidence": "low"
            }

        return suggestions


# ============== Convenience Functions ==============

def classify_content_dimensions(
    content: str,
    competitor_name: str
) -> List[Tuple[str, float]]:
    """Quick function to classify content by dimensions."""
    analyzer = DimensionAnalyzer()
    return analyzer.classify_article_dimension("", content, competitor_name)


def analyze_review_for_dimensions(
    review_text: str,
    rating: float,
    competitor_name: str
) -> Dict[str, int]:
    """Quick function to analyze a review for dimension signals."""
    analyzer = DimensionAnalyzer()
    return analyzer.analyze_review_dimensions(review_text, rating, competitor_name)
