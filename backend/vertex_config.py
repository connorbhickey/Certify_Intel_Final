"""
Certify Intel - Vertex AI Configuration (v5.3.0)
Centralized configuration management for Vertex AI integration.

This module provides:
- Environment variable management
- Configuration validation
- Security settings
- Cost tracking configuration
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class VertexAIModel(Enum):
    """Available Vertex AI models."""
    # Gemini 3 Series (Latest)
    GEMINI_3_FLASH = "gemini-3-flash"
    GEMINI_3_PRO = "gemini-3-pro"

    # Gemini 2.5 Series
    GEMINI_25_FLASH = "gemini-2.5-flash"
    GEMINI_25_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_25_PRO = "gemini-2.5-pro"

    # Healthcare-specific (requires approval)
    MEDLM_MEDIUM = "medlm-medium"
    MEDLM_LARGE = "medlm-large"


class VertexAILocation(Enum):
    """Available Vertex AI locations."""
    US_CENTRAL1 = "us-central1"
    US_EAST1 = "us-east1"
    US_EAST4 = "us-east4"
    US_WEST1 = "us-west1"
    US_WEST4 = "us-west4"
    EUROPE_WEST1 = "europe-west1"
    EUROPE_WEST4 = "europe-west4"
    ASIA_NORTHEAST1 = "asia-northeast1"
    ASIA_SOUTHEAST1 = "asia-southeast1"


@dataclass
class ModelPricing:
    """Pricing information for a model."""
    input_per_1m: float  # Cost per 1M input tokens
    output_per_1m: float  # Cost per 1M output tokens
    context_window: int  # Max context size
    output_limit: int  # Max output tokens


# Model pricing as of 2026
MODEL_PRICING: Dict[str, ModelPricing] = {
    "gemini-3-flash": ModelPricing(0.10, 0.40, 1_000_000, 8192),
    "gemini-3-pro": ModelPricing(1.50, 12.00, 1_000_000, 8192),
    "gemini-2.5-flash": ModelPricing(0.075, 0.30, 1_000_000, 8192),
    "gemini-2.5-flash-lite": ModelPricing(0.01875, 0.075, 1_000_000, 8192),
    "gemini-2.5-pro": ModelPricing(1.25, 10.00, 2_000_000, 8192),
    "medlm-medium": ModelPricing(0.50, 1.50, 32_000, 4096),
    "medlm-large": ModelPricing(1.00, 3.00, 32_000, 4096),
}


@dataclass
class VertexAISettings:
    """Complete Vertex AI settings."""
    # Required
    project_id: str
    location: str = "us-central1"

    # Model settings
    default_model: str = "gemini-3-flash-preview"
    executive_summary_model: str = "gemini-3-pro-preview"
    extraction_model: str = "gemini-3-flash-preview"
    bulk_model: str = "gemini-3-flash-preview"

    # Generation defaults
    temperature: float = 0.1
    max_output_tokens: int = 8192
    top_p: float = 0.95
    top_k: int = 40

    # RAG settings (Phase 2)
    rag_enabled: bool = False
    rag_corpus_prefix: str = "certify_intel"
    rag_top_k: int = 5

    # Vector Search settings (Phase 3)
    vector_search_enabled: bool = False
    vector_search_index: Optional[str] = None
    embedding_model: str = "text-embedding-004"

    # Agent settings (Phase 4)
    agent_enabled: bool = False
    agent_id: Optional[str] = None

    # Security settings
    enable_audit_logging: bool = True
    enable_vpc_sc: bool = False
    cmek_key: Optional[str] = None

    # Cost tracking
    monthly_budget_usd: float = 100.0
    cost_alert_threshold: float = 0.8  # Alert at 80% of budget

    # Feature flags
    enable_grounding: bool = True
    enable_multimodal: bool = True
    enable_streaming: bool = True


def load_vertex_settings() -> VertexAISettings:
    """
    Load Vertex AI settings from environment variables.

    Environment variables:
        GOOGLE_CLOUD_PROJECT or GCP_PROJECT_ID: GCP project ID
        VERTEX_AI_LOCATION: GCP region (default: us-central1)
        VERTEX_AI_MODEL: Default model (default: gemini-2.5-flash)
        VERTEX_AI_TEMPERATURE: Generation temperature (default: 0.1)
        VERTEX_AI_RAG_ENABLED: Enable RAG features (default: false)
        VERTEX_AI_VECTOR_SEARCH_ENABLED: Enable Vector Search (default: false)
        VERTEX_AI_AGENT_ENABLED: Enable Agent Builder (default: false)
        VERTEX_AI_MONTHLY_BUDGET: Monthly budget in USD (default: 100)

    Returns:
        VertexAISettings instance
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID", "")

    return VertexAISettings(
        project_id=project_id,
        location=os.getenv("VERTEX_AI_LOCATION", "us-central1"),
        default_model=os.getenv("VERTEX_AI_MODEL", "gemini-3-flash-preview"),
        executive_summary_model=os.getenv("VERTEX_AI_SUMMARY_MODEL", "gemini-3-pro-preview"),
        extraction_model=os.getenv("VERTEX_AI_EXTRACTION_MODEL", "gemini-3-flash-preview"),
        bulk_model=os.getenv("VERTEX_AI_BULK_MODEL", "gemini-3-flash-preview"),
        temperature=float(os.getenv("VERTEX_AI_TEMPERATURE", "0.1")),
        max_output_tokens=int(os.getenv("VERTEX_AI_MAX_TOKENS", "8192")),
        rag_enabled=os.getenv("VERTEX_AI_RAG_ENABLED", "").lower() == "true",
        rag_corpus_prefix=os.getenv("VERTEX_AI_RAG_PREFIX", "certify_intel"),
        vector_search_enabled=os.getenv("VERTEX_AI_VECTOR_SEARCH_ENABLED", "").lower() == "true",
        vector_search_index=os.getenv("VERTEX_AI_VECTOR_INDEX"),
        agent_enabled=os.getenv("VERTEX_AI_AGENT_ENABLED", "").lower() == "true",
        agent_id=os.getenv("VERTEX_AI_AGENT_ID"),
        enable_audit_logging=os.getenv("VERTEX_AI_AUDIT_LOGGING", "true").lower() == "true",
        enable_vpc_sc=os.getenv("VERTEX_AI_VPC_SC", "").lower() == "true",
        cmek_key=os.getenv("VERTEX_AI_CMEK_KEY"),
        monthly_budget_usd=float(os.getenv("VERTEX_AI_MONTHLY_BUDGET", "100")),
        cost_alert_threshold=float(os.getenv("VERTEX_AI_COST_ALERT_THRESHOLD", "0.8")),
        enable_grounding=os.getenv("VERTEX_AI_GROUNDING", "true").lower() == "true",
        enable_multimodal=os.getenv("VERTEX_AI_MULTIMODAL", "true").lower() == "true",
        enable_streaming=os.getenv("VERTEX_AI_STREAMING", "true").lower() == "true",
    )


def validate_settings(settings: VertexAISettings) -> Dict[str, Any]:
    """
    Validate Vertex AI settings.

    Args:
        settings: VertexAISettings to validate

    Returns:
        Dictionary with validation results
    """
    errors = []
    warnings = []

    # Required settings
    if not settings.project_id:
        errors.append("GCP project ID not configured (set GOOGLE_CLOUD_PROJECT)")

    # Model validation
    valid_models = [m.value for m in VertexAIModel]
    if settings.default_model not in valid_models:
        warnings.append(f"Unknown model: {settings.default_model}")

    # Location validation
    valid_locations = [loc.value for loc in VertexAILocation]
    if settings.location not in valid_locations:
        warnings.append(f"Unknown location: {settings.location}")

    # Feature dependency checks
    if settings.rag_enabled and not settings.project_id:
        errors.append("RAG requires a GCP project")

    if settings.vector_search_enabled and not settings.vector_search_index:
        warnings.append("Vector Search enabled but no index configured")

    if settings.agent_enabled and not settings.agent_id:
        warnings.append("Agent Builder enabled but no agent ID configured")

    # Security checks
    if settings.enable_vpc_sc and not settings.project_id:
        errors.append("VPC Service Controls requires a GCP project")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "settings": {
            "project_id": settings.project_id,
            "location": settings.location,
            "default_model": settings.default_model,
            "rag_enabled": settings.rag_enabled,
            "vector_search_enabled": settings.vector_search_enabled,
            "agent_enabled": settings.agent_enabled,
        }
    }


def get_model_pricing(model: str) -> Optional[ModelPricing]:
    """Get pricing information for a model."""
    return MODEL_PRICING.get(model)


def estimate_monthly_cost(
    input_tokens_per_day: int,
    output_tokens_per_day: int,
    model: str = "gemini-2.5-flash"
) -> Dict[str, float]:
    """
    Estimate monthly cost based on daily usage.

    Args:
        input_tokens_per_day: Average daily input tokens
        output_tokens_per_day: Average daily output tokens
        model: Model to use for pricing

    Returns:
        Dictionary with cost breakdown
    """
    pricing = get_model_pricing(model)
    if not pricing:
        return {"error": f"Unknown model: {model}"}

    daily_input_cost = (input_tokens_per_day / 1_000_000) * pricing.input_per_1m
    daily_output_cost = (output_tokens_per_day / 1_000_000) * pricing.output_per_1m
    daily_total = daily_input_cost + daily_output_cost

    return {
        "model": model,
        "daily_input_cost": round(daily_input_cost, 4),
        "daily_output_cost": round(daily_output_cost, 4),
        "daily_total": round(daily_total, 4),
        "monthly_estimate": round(daily_total * 30, 2),
        "yearly_estimate": round(daily_total * 365, 2),
    }


# Task routing configuration
TASK_MODEL_ROUTING = {
    # High-volume, low-complexity tasks -> fast model
    "bulk_extraction": "gemini-3-flash-preview",
    "news_classification": "gemini-3-flash-preview",
    "sentiment_analysis": "gemini-3-flash-preview",

    # Standard tasks -> fast model
    "data_extraction": "gemini-3-flash-preview",
    "competitor_analysis": "gemini-3-flash-preview",
    "dimension_scoring": "gemini-3-flash-preview",

    # Complex tasks -> quality model
    "executive_summary": "gemini-3-pro-preview",
    "battlecard_generation": "gemini-3-pro-preview",
    "strategic_analysis": "gemini-3-pro-preview",

    # Advanced features -> newest models
    "agent_reasoning": "gemini-3-flash-preview",
    "complex_qa": "gemini-3-pro-preview",

    # Multimodal tasks
    "image_analysis": "gemini-3-flash-preview",
    "document_analysis": "gemini-3-flash-preview",
    "video_analysis": "gemini-3-flash-preview",
}


def get_model_for_task(task_type: str) -> str:
    """Get recommended model for a specific task type."""
    return TASK_MODEL_ROUTING.get(task_type, "gemini-3-flash-preview")


# Export configuration status on import
_settings = load_vertex_settings()
_validation = validate_settings(_settings)

if _validation["errors"]:
    logger.warning(f"Vertex AI configuration errors: {_validation['errors']}")
if _validation["warnings"]:
    logger.info(f"Vertex AI configuration warnings: {_validation['warnings']}")

# Expose current settings
current_settings = _settings
is_configured = _validation["valid"]
