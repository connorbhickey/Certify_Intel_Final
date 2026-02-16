"""
Confidence Scoring Module for Certify Intel
Based on Admiralty Code framework for intelligence reliability assessment.

Reference: https://en.wikipedia.org/wiki/Intelligence_source_and_information_reliability
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass, field


# Source type definitions with default reliability ratings
SOURCE_TYPE_DEFAULTS = {
    "sec_filing": {"reliability": "A", "credibility": 1, "description": "Legally mandated SEC disclosures"},
    "api_verified": {"reliability": "B", "credibility": 2, "description": "Official API data (G2, LinkedIn)"},
    "klas_report": {"reliability": "B", "credibility": 2, "description": "Industry analyst research"},
    "definitive_hc": {"reliability": "B", "credibility": 2, "description": "Definitive Healthcare market data"},
    "manual_verified": {"reliability": "B", "credibility": 2, "description": "Human-verified entry"},
    "website_scrape": {"reliability": "D", "credibility": 4, "description": "Marketing website content"},
    "news_article": {"reliability": "C", "credibility": 3, "description": "Press releases, news"},
    "linkedin_estimate": {"reliability": "D", "credibility": 4, "description": "LinkedIn employee count estimate"},
    "crunchbase": {"reliability": "D", "credibility": 4, "description": "Startup database info"},
    "glassdoor": {"reliability": "C", "credibility": 4, "description": "Employee reviews platform"},
    "unknown": {"reliability": "F", "credibility": 6, "description": "Source not documented"},
}

# Admiralty Code reliability ratings
RELIABILITY_SCORES = {
    "A": 50,  # Completely reliable
    "B": 40,  # Usually reliable
    "C": 30,  # Fairly reliable
    "D": 20,  # Not usually reliable
    "E": 10,  # Unreliable
    "F": 5,   # Reliability cannot be judged
}

RELIABILITY_DESCRIPTIONS = {
    "A": "Completely Reliable - No doubt about authenticity, trustworthiness, or competency; has a history of complete reliability",
    "B": "Usually Reliable - Minor doubt about authenticity, trustworthiness, or competency; has a history of valid information most of the time",
    "C": "Fairly Reliable - Doubt about authenticity, trustworthiness, or competency; has provided valid information in the past",
    "D": "Not Usually Reliable - Significant doubt about authenticity, trustworthiness, or competency; has provided valid information in the past",
    "E": "Unreliable - Lacking in authenticity, trustworthiness, and competency; history of invalid information",
    "F": "Reliability Cannot Be Judged - No basis for evaluating reliability",
}

# Admiralty Code information credibility ratings
CREDIBILITY_SCORES = {
    1: 30,  # Confirmed by other sources
    2: 25,  # Probably true
    3: 20,  # Possibly true
    4: 15,  # Doubtfully true
    5: 10,  # Improbable
    6: 5,   # Truth cannot be judged
}

CREDIBILITY_DESCRIPTIONS = {
    1: "Confirmed - Confirmed by other independent sources; logical in itself; consistent with other information on the subject",
    2: "Probably True - Not confirmed; logical in itself; consistent with other information on the subject",
    3: "Possibly True - Not confirmed; reasonably logical in itself; agrees with some other information on the subject",
    4: "Doubtfully True - Not confirmed; possible but not logical; no other information on the subject",
    5: "Improbable - Not confirmed; not logical in itself; contradicted by other information on the subject",
    6: "Truth Cannot Be Judged - No basis for evaluating the validity of the information",
}

# Source type bonuses/penalties
SOURCE_TYPE_BONUSES = {
    "sec_filing": 10,       # Legally required disclosures
    "api_verified": 8,      # Structured data from official APIs
    "klas_report": 8,       # Industry analyst reports
    "definitive_hc": 8,     # Healthcare market data
    "manual_verified": 5,   # Human-verified
    "website_scrape": 0,    # Marketing content
    "news_article": -2,     # May be outdated/inaccurate
    "linkedin_estimate": 0, # Proxy metric
    "crunchbase": 0,        # Startup database
    "glassdoor": 0,         # Employee reviews
    "unknown": -10,         # Unknown sources penalized
}


@dataclass
class ConfidenceResult:
    """Result of confidence score calculation."""
    score: int  # 0-100
    level: str  # "high", "moderate", "low"
    explanation: str
    breakdown: Dict[str, int] = field(default_factory=dict)


def calculate_confidence_score(
    source_type: str,
    source_reliability: Optional[str] = None,
    information_credibility: Optional[int] = None,
    corroborating_sources: int = 0,
    data_age_days: int = 0
) -> ConfidenceResult:
    """
    Calculate composite confidence score using Admiralty Code framework.

    Args:
        source_type: Type of data source (e.g., "website_scrape", "sec_filing")
        source_reliability: A-F scale for source reliability (optional, will use default for source_type)
        information_credibility: 1-6 scale for information credibility (optional, will use default)
        corroborating_sources: Number of additional sources that agree with this data
        data_age_days: How many days old the data is

    Returns:
        ConfidenceResult with score (0-100), level, explanation, and breakdown
    """

    # Get defaults from source type if not provided
    defaults = SOURCE_TYPE_DEFAULTS.get(source_type, SOURCE_TYPE_DEFAULTS["unknown"])

    if source_reliability is None:
        source_reliability = defaults["reliability"]
    if information_credibility is None:
        information_credibility = defaults["credibility"]

    # Calculate reliability score (max 50 points)
    reliability_score = RELIABILITY_SCORES.get(source_reliability.upper(), 5)

    # Calculate credibility score (max 30 points)
    credibility_score = CREDIBILITY_SCORES.get(information_credibility, 5)

    # Corroboration bonus (max 15 points, 5 per corroborating source)
    corroboration_bonus = min(corroborating_sources * 5, 15)

    # Freshness penalty (lose 1 point per 30 days, max -15)
    freshness_penalty = min(data_age_days // 30, 15)

    # Source type bonus/penalty
    source_bonus = SOURCE_TYPE_BONUSES.get(source_type, 0)

    # Calculate composite score
    raw_score = reliability_score + credibility_score + corroboration_bonus + source_bonus - freshness_penalty
    final_score = max(0, min(100, raw_score))

    # Determine confidence level based on National Intelligence Council standards
    if final_score >= 70:
        level = "high"
        explanation = "High confidence based on reliable, corroborated information from trusted sources"
    elif final_score >= 40:
        level = "moderate"
        explanation = "Moderate confidence; credible information with limited corroboration or source reliability"
    else:
        level = "low"
        explanation = "Low confidence; unverified claims or sources with limited reliability history"

    # Build detailed breakdown
    breakdown = {
        "reliability_score": reliability_score,
        "credibility_score": credibility_score,
        "corroboration_bonus": corroboration_bonus,
        "source_bonus": source_bonus,
        "freshness_penalty": -freshness_penalty,
        "raw_score": raw_score,
        "final_score": final_score,
    }

    return ConfidenceResult(
        score=final_score,
        level=level,
        explanation=explanation,
        breakdown=breakdown
    )


def get_source_defaults(source_type: str) -> Dict:
    """Get default reliability and credibility for a source type."""
    return SOURCE_TYPE_DEFAULTS.get(source_type, SOURCE_TYPE_DEFAULTS["unknown"])


def calculate_data_staleness(extracted_at: datetime, data_as_of_date: Optional[datetime] = None) -> int:
    """
    Calculate how stale data is in days.

    Args:
        extracted_at: When the data was extracted
        data_as_of_date: When the data was actually true (if known)

    Returns:
        Number of days since the data was current
    """
    reference_date = data_as_of_date or extracted_at
    delta = datetime.utcnow() - reference_date
    return max(0, delta.days)


def determine_confidence_level_from_score(score: int) -> str:
    """Convert numeric score to confidence level."""
    if score >= 70:
        return "high"
    elif score >= 40:
        return "moderate"
    else:
        return "low"


@dataclass
class TriangulationResult:
    """Result of multi-source data triangulation."""
    best_value: str
    confidence_level: str
    confidence_score: int
    source_used: str
    all_sources: Dict
    discrepancy_flag: bool
    review_reason: Optional[str] = None


def triangulate_data_points(sources: List[Dict]) -> TriangulationResult:
    """
    Triangulate data from multiple sources to determine best value.

    Args:
        sources: List of source dictionaries with keys:
            - value: The data value
            - source_type: Type of source
            - reliability: A-F reliability rating
            - credibility: 1-6 credibility rating

    Returns:
        TriangulationResult with best value and confidence assessment
    """
    if not sources:
        return TriangulationResult(
            best_value="Unknown",
            confidence_level="low",
            confidence_score=0,
            source_used="none",
            all_sources={},
            discrepancy_flag=True,
            review_reason="No sources available"
        )

    # Authority order for selecting best source
    authority_order = ["sec_filing", "api_verified", "klas_report", "definitive_hc", "manual_verified"]

    # Check for authoritative source
    for auth_type in authority_order:
        for source in sources:
            if source.get("source_type") == auth_type and source.get("value"):
                confidence = calculate_confidence_score(
                    source_type=auth_type,
                    source_reliability=source.get("reliability"),
                    information_credibility=source.get("credibility"),
                    corroborating_sources=len(sources) - 1
                )
                return TriangulationResult(
                    best_value=source["value"],
                    confidence_level=confidence.level,
                    confidence_score=confidence.score,
                    source_used=auth_type,
                    all_sources={s.get("source_type", "unknown"): s for s in sources},
                    discrepancy_flag=False
                )

    # No authoritative source - check for consensus
    values_with_sources = [(s.get("value"), s) for s in sources if s.get("value")]

    if not values_with_sources:
        return TriangulationResult(
            best_value="Unknown",
            confidence_level="low",
            confidence_score=0,
            source_used="none",
            all_sources={s.get("source_type", "unknown"): s for s in sources},
            discrepancy_flag=True,
            review_reason="No values available from any source"
        )

    # Return first available value with low confidence
    best_source = values_with_sources[0][1]
    source_type = best_source.get("source_type", "unknown")

    confidence = calculate_confidence_score(
        source_type=source_type,
        source_reliability=best_source.get("reliability"),
        information_credibility=best_source.get("credibility"),
        corroborating_sources=0
    )

    return TriangulationResult(
        best_value=values_with_sources[0][0],
        confidence_level=confidence.level,
        confidence_score=confidence.score,
        source_used=source_type,
        all_sources={s.get("source_type", "unknown"): s for s in sources},
        discrepancy_flag=True,
        review_reason="No authoritative source; values not corroborated by multiple reliable sources"
    )


def get_reliability_description(reliability: str) -> str:
    """Get human-readable description for reliability rating."""
    return RELIABILITY_DESCRIPTIONS.get(reliability.upper(), "Unknown reliability rating")


def get_credibility_description(credibility: int) -> str:
    """Get human-readable description for credibility rating."""
    return CREDIBILITY_DESCRIPTIONS.get(credibility, "Unknown credibility rating")


def get_source_type_description(source_type: str) -> str:
    """Get human-readable description for source type."""
    defaults = SOURCE_TYPE_DEFAULTS.get(source_type, SOURCE_TYPE_DEFAULTS["unknown"])
    return defaults.get("description", "Unknown source type")
