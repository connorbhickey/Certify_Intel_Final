"""
Certify Intel - ML-Powered Sentiment Analysis (v5.0.5)
Uses Hugging Face transformers for accurate sentiment classification.

Replaces keyword-based sentiment with ML models for better accuracy.

Models:
- distilbert-base-uncased-finetuned-sst-2-english: Fast, accurate for general sentiment
- ProsusAI/finbert: Specialized for financial news sentiment

v5.0.5: Added for Live News Feed Phase 4 - AI-Powered Enhancements
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import transformers
try:
    from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("Transformers not installed. Run: pip install transformers torch")


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    label: str  # positive, negative, neutral
    score: float  # confidence score 0-1
    model: str  # model used
    latency_ms: float


class MLSentimentAnalyzer:
    """
    ML-powered sentiment analyzer using Hugging Face models.

    Supports multiple models for different use cases:
    - general: Fast general-purpose sentiment
    - financial: Specialized for financial/business news
    - multilingual: For non-English text
    """

    # Available models
    MODELS = {
        "general": "distilbert-base-uncased-finetuned-sst-2-english",
        "financial": "ProsusAI/finbert",
        "multilingual": "nlptown/bert-base-multilingual-uncased-sentiment",
    }

    # Label mapping for different models
    LABEL_MAPPING = {
        "distilbert-base-uncased-finetuned-sst-2-english": {
            "POSITIVE": "positive",
            "NEGATIVE": "negative",
        },
        "ProsusAI/finbert": {
            "positive": "positive",
            "negative": "negative",
            "neutral": "neutral",
        },
        "nlptown/bert-base-multilingual-uncased-sentiment": {
            "1 star": "negative",
            "2 stars": "negative",
            "3 stars": "neutral",
            "4 stars": "positive",
            "5 stars": "positive",
        },
    }

    def __init__(self, model_type: str = "general", use_gpu: bool = False):
        """
        Initialize ML sentiment analyzer.

        Args:
            model_type: Type of model to use (general, financial, multilingual)
            use_gpu: Whether to use GPU if available
        """
        self.model_type = model_type
        self.model_name = self.MODELS.get(model_type, self.MODELS["general"])
        self.device = 0 if use_gpu and torch.cuda.is_available() else -1 if TRANSFORMERS_AVAILABLE else None
        self.pipeline = None
        self._initialized = False

        if TRANSFORMERS_AVAILABLE:
            self._initialize_pipeline()

    def _initialize_pipeline(self):
        """Initialize the sentiment analysis pipeline."""
        try:
            logger.info(f"Loading sentiment model: {self.model_name}")
            self.pipeline = pipeline(
                "sentiment-analysis",
                model=self.model_name,
                device=self.device,
                truncation=True,
                max_length=512,
            )
            self._initialized = True
            logger.info(f"Sentiment model loaded successfully: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to load sentiment model: {e}")
            self._initialized = False

    @property
    def is_available(self) -> bool:
        """Check if the analyzer is available and initialized."""
        return TRANSFORMERS_AVAILABLE and self._initialized

    def analyze(self, text: str) -> SentimentResult:
        """
        Analyze sentiment of a single text.

        Args:
            text: Text to analyze

        Returns:
            SentimentResult with label, score, and metadata
        """
        if not self.is_available:
            # Fallback to keyword-based if ML not available
            return self._keyword_fallback(text)

        start_time = datetime.now()

        try:
            # Truncate very long texts
            if len(text) > 1000:
                text = text[:1000]

            result = self.pipeline(text)[0]

            # Map label to standard format
            label_map = self.LABEL_MAPPING.get(self.model_name, {})
            raw_label = result["label"]
            label = label_map.get(raw_label, raw_label.lower())

            # Handle models without neutral class
            if label not in ["positive", "negative", "neutral"]:
                # If score is not confident, mark as neutral
                if result["score"] < 0.7:
                    label = "neutral"
                else:
                    label = "positive" if "POSITIVE" in raw_label.upper() else "negative"

            latency = (datetime.now() - start_time).total_seconds() * 1000

            return SentimentResult(
                label=label,
                score=result["score"],
                model=self.model_name,
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return self._keyword_fallback(text)

    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """
        Analyze sentiment of multiple texts efficiently.

        Args:
            texts: List of texts to analyze

        Returns:
            List of SentimentResult objects
        """
        if not self.is_available:
            return [self._keyword_fallback(t) for t in texts]

        start_time = datetime.now()

        try:
            # Truncate very long texts
            processed_texts = [t[:1000] if len(t) > 1000 else t for t in texts]

            results = self.pipeline(processed_texts)

            label_map = self.LABEL_MAPPING.get(self.model_name, {})
            latency = (datetime.now() - start_time).total_seconds() * 1000
            per_text_latency = latency / len(texts) if texts else 0

            sentiment_results = []
            for result in results:
                raw_label = result["label"]
                label = label_map.get(raw_label, raw_label.lower())

                if label not in ["positive", "negative", "neutral"]:
                    if result["score"] < 0.7:
                        label = "neutral"
                    else:
                        label = "positive" if "POSITIVE" in raw_label.upper() else "negative"

                sentiment_results.append(SentimentResult(
                    label=label,
                    score=result["score"],
                    model=self.model_name,
                    latency_ms=per_text_latency
                ))

            return sentiment_results

        except Exception as e:
            logger.error(f"Batch sentiment analysis failed: {e}")
            return [self._keyword_fallback(t) for t in texts]

    def _keyword_fallback(self, text: str) -> SentimentResult:
        """Fallback to keyword-based sentiment when ML is unavailable."""
        text_lower = text.lower()

        positive_keywords = [
            "growth", "success", "award", "wins", "leading", "innovative",
            "raises", "expands", "partnership", "launch", "revenue", "profit",
            "record", "milestone", "breakthrough", "exceeded", "strong"
        ]
        negative_keywords = [
            "layoffs", "lawsuit", "breach", "decline", "struggles", "loses",
            "cuts", "failed", "downturn", "loss", "lawsuit", "investigation",
            "recall", "warning", "risk", "debt", "bankruptcy"
        ]

        positive_count = sum(1 for word in positive_keywords if word in text_lower)
        negative_count = sum(1 for word in negative_keywords if word in text_lower)

        if positive_count > negative_count:
            label = "positive"
            score = min(0.9, 0.5 + (positive_count * 0.1))
        elif negative_count > positive_count:
            label = "negative"
            score = min(0.9, 0.5 + (negative_count * 0.1))
        else:
            label = "neutral"
            score = 0.5

        return SentimentResult(
            label=label,
            score=score,
            model="keyword_fallback",
            latency_ms=0.1
        )


class FinancialSentimentAnalyzer(MLSentimentAnalyzer):
    """
    Specialized sentiment analyzer for financial and business news.

    Uses FinBERT model which is trained on financial text and provides
    more accurate sentiment for business-related content.
    """

    def __init__(self, use_gpu: bool = False):
        """Initialize with financial model."""
        super().__init__(model_type="financial", use_gpu=use_gpu)


class NewsHeadlineSentimentAnalyzer:
    """
    Optimized sentiment analyzer for news headlines.

    Handles short text better and provides additional context
    for news-specific sentiment analysis.
    """

    def __init__(self, model_type: str = "financial", use_gpu: bool = False):
        """
        Initialize news headline analyzer.

        Args:
            model_type: Model to use (general or financial)
            use_gpu: Whether to use GPU
        """
        self.analyzer = MLSentimentAnalyzer(model_type=model_type, use_gpu=use_gpu)

        # News-specific keyword boosters
        self.positive_boosters = {
            "funding", "acquisition", "partnership", "launch", "expansion",
            "growth", "profit", "milestone", "award", "breakthrough"
        }
        self.negative_boosters = {
            "layoff", "lawsuit", "breach", "decline", "loss", "bankruptcy",
            "investigation", "recall", "warning", "shutdown", "downturn"
        }

    @property
    def is_available(self) -> bool:
        """Check if analyzer is available."""
        return self.analyzer.is_available

    def analyze_headline(self, headline: str, snippet: str = "") -> SentimentResult:
        """
        Analyze a news headline with optional snippet context.

        Args:
            headline: News headline
            snippet: Optional article snippet for context

        Returns:
            SentimentResult
        """
        # Combine headline and snippet for better context
        text = headline
        if snippet:
            text = f"{headline}. {snippet[:200]}"

        result = self.analyzer.analyze(text)

        # Apply news-specific adjustments
        text_lower = text.lower()

        # Check for strong indicators
        has_positive_booster = any(word in text_lower for word in self.positive_boosters)
        has_negative_booster = any(word in text_lower for word in self.negative_boosters)

        # Adjust confidence for strong indicators
        if has_positive_booster and result.label == "positive":
            result = SentimentResult(
                label=result.label,
                score=min(0.95, result.score + 0.1),
                model=result.model,
                latency_ms=result.latency_ms
            )
        elif has_negative_booster and result.label == "negative":
            result = SentimentResult(
                label=result.label,
                score=min(0.95, result.score + 0.1),
                model=result.model,
                latency_ms=result.latency_ms
            )

        return result

    def analyze_headlines_batch(
        self,
        headlines: List[Tuple[str, str]]
    ) -> List[SentimentResult]:
        """
        Analyze multiple headlines efficiently.

        Args:
            headlines: List of (headline, snippet) tuples

        Returns:
            List of SentimentResult objects
        """
        texts = [
            f"{h}. {s[:200]}" if s else h
            for h, s in headlines
        ]

        results = self.analyzer.analyze_batch(texts)

        # Apply news-specific adjustments
        adjusted_results = []
        for i, (result, (headline, snippet)) in enumerate(zip(results, headlines)):
            text_lower = f"{headline} {snippet}".lower()

            has_positive_booster = any(word in text_lower for word in self.positive_boosters)
            has_negative_booster = any(word in text_lower for word in self.negative_boosters)

            if has_positive_booster and result.label == "positive":
                result = SentimentResult(
                    label=result.label,
                    score=min(0.95, result.score + 0.1),
                    model=result.model,
                    latency_ms=result.latency_ms
                )
            elif has_negative_booster and result.label == "negative":
                result = SentimentResult(
                    label=result.label,
                    score=min(0.95, result.score + 0.1),
                    model=result.model,
                    latency_ms=result.latency_ms
                )

            adjusted_results.append(result)

        return adjusted_results


# ============== INTEGRATION WITH NEWS MONITOR ==============

def get_sentiment_analyzer(model_type: str = "financial") -> MLSentimentAnalyzer:
    """
    Get a configured sentiment analyzer.

    Args:
        model_type: Type of model (general, financial, multilingual)

    Returns:
        MLSentimentAnalyzer instance
    """
    use_gpu = os.getenv("ML_USE_GPU", "false").lower() == "true"
    return MLSentimentAnalyzer(model_type=model_type, use_gpu=use_gpu)


def get_headline_analyzer() -> NewsHeadlineSentimentAnalyzer:
    """
    Get a news headline sentiment analyzer.

    Returns:
        NewsHeadlineSentimentAnalyzer instance
    """
    use_gpu = os.getenv("ML_USE_GPU", "false").lower() == "true"
    model_type = os.getenv("ML_SENTIMENT_MODEL", "financial")
    return NewsHeadlineSentimentAnalyzer(model_type=model_type, use_gpu=use_gpu)


def analyze_news_sentiment(headline: str, snippet: str = "") -> Dict[str, Any]:
    """
    Analyze sentiment of a news article.

    Convenience function for quick sentiment analysis.

    Args:
        headline: News headline
        snippet: Article snippet

    Returns:
        Dictionary with sentiment analysis results
    """
    analyzer = get_headline_analyzer()
    result = analyzer.analyze_headline(headline, snippet)

    return {
        "sentiment": result.label,
        "confidence": result.score,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "ml_powered": result.model != "keyword_fallback"
    }


def analyze_news_batch(
    articles: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    Analyze sentiment of multiple news articles efficiently.

    Args:
        articles: List of dicts with 'title' and optional 'snippet' keys

    Returns:
        List of sentiment analysis results
    """
    analyzer = get_headline_analyzer()

    headlines = [
        (a.get("title", ""), a.get("snippet", ""))
        for a in articles
    ]

    results = analyzer.analyze_headlines_batch(headlines)

    return [
        {
            "sentiment": r.label,
            "confidence": r.score,
            "model": r.model,
            "latency_ms": r.latency_ms,
            "ml_powered": r.model != "keyword_fallback"
        }
        for r in results
    ]


# ============== TEST FUNCTION ==============

def test_ml_sentiment():
    """Test the ML sentiment analyzer."""
    print("Testing ML Sentiment Analyzer...")
    print("-" * 50)

    if not TRANSFORMERS_AVAILABLE:
        print("Transformers not installed. Run: pip install transformers torch")
        return

    # Test general analyzer
    print("\n1. Testing General Sentiment Analyzer...")
    analyzer = MLSentimentAnalyzer(model_type="general")

    if not analyzer.is_available:
        print("   Model not loaded. Check installation.")
        return

    test_texts = [
        "Company announces record profits and expansion plans",
        "Layoffs hit tech sector as revenue declines sharply",
        "Healthcare company reports quarterly results in line with expectations",
    ]

    for text in test_texts:
        result = analyzer.analyze(text)
        print(f"   Text: {text[:50]}...")
        print(f"   Sentiment: {result.label} (confidence: {result.score:.2f})")
        print()

    # Test headline analyzer
    print("2. Testing News Headline Analyzer...")
    headline_analyzer = get_headline_analyzer()

    headlines = [
        ("Phreesia Raises $100M in Series D Funding", "Patient intake company secures funding for expansion"),
        ("Epic Systems Faces Lawsuit Over Data Practices", "Healthcare IT giant under scrutiny"),
        ("athenahealth Partners with Major Hospital Chain", "Integration deal announced"),
    ]

    for headline, snippet in headlines:
        result = headline_analyzer.analyze_headline(headline, snippet)
        print(f"   Headline: {headline}")
        print(f"   Sentiment: {result.label} (confidence: {result.score:.2f})")
        print()

    # Test batch processing
    print("3. Testing Batch Processing...")
    results = headline_analyzer.analyze_headlines_batch(headlines)
    print(f"   Processed {len(results)} headlines")
    print(f"   Positive: {sum(1 for r in results if r.label == 'positive')}")
    print(f"   Negative: {sum(1 for r in results if r.label == 'negative')}")
    print(f"   Neutral: {sum(1 for r in results if r.label == 'neutral')}")

    print("\n" + "-" * 50)
    print("ML Sentiment Analyzer test complete!")


if __name__ == "__main__":
    test_ml_sentiment()
