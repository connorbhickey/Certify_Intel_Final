"""
Certify Intel - Competitor Pydantic Schemas
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class CompetitorCreate(BaseModel):
    name: str
    website: Optional[str] = None
    status: str = "Active"
    threat_level: str = "Medium"
    notes: Optional[str] = None
    pricing_model: Optional[str] = None
    base_price: Optional[str] = None
    price_unit: Optional[str] = None
    product_categories: Optional[str] = None
    key_features: Optional[str] = None
    integration_partners: Optional[str] = None
    certifications: Optional[str] = None
    target_segments: Optional[str] = None
    customer_size_focus: Optional[str] = None
    geographic_focus: Optional[str] = None
    customer_count: Optional[str] = None
    customer_acquisition_rate: Optional[str] = None
    key_customers: Optional[str] = None
    g2_rating: Optional[str] = None
    employee_count: Optional[str] = None
    employee_growth_rate: Optional[str] = None
    year_founded: Optional[str] = None
    headquarters: Optional[str] = None
    funding_total: Optional[str] = None
    latest_round: Optional[str] = None
    pe_vc_backers: Optional[str] = None
    website_traffic: Optional[str] = None
    social_following: Optional[str] = None
    recent_launches: Optional[str] = None
    news_mentions: Optional[str] = None


class CompetitorResponse(CompetitorCreate):
    id: int
    last_updated: datetime
    data_quality_score: Optional[float] = None
    created_at: datetime
    is_public: Optional[bool] = False
    ticker_symbol: Optional[str] = None
    stock_exchange: Optional[str] = None
    ai_threat_summary: Optional[str] = None

    class Config:
        from_attributes = True


class CorrectionRequest(BaseModel):
    field: str
    new_value: str
    reason: Optional[str] = "Manual Correction"
    source_url: Optional[str] = None


class ScrapeRequest(BaseModel):
    competitor_id: int
    pages_to_scrape: List[str] = ["homepage", "pricing", "about"]


class BulkUpdateRequest(BaseModel):
    """Request model for bulk update by IDs."""
    ids: list[int]
    updates: dict


class BulkDeleteRequest(BaseModel):
    """Request model for bulk delete."""
    ids: list[int]


class BulkExportRequest(BaseModel):
    """Request model for bulk export."""
    ids: list[int]
    format: str = "excel"


class SearchResult(BaseModel):
    type: str  # competitor, product, news, knowledge
    id: int
    title: str
    subtitle: Optional[str] = None
    snippet: Optional[str] = None
    score: float = 1.0
    url: Optional[str] = None
