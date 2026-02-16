"""
Certify Intel - Product & Pricing Pydantic Schemas
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ProductCreate(BaseModel):
    """Create a new competitor product."""
    competitor_id: int
    product_name: str
    product_category: str  # "Patient Intake", "RCM", "EHR", "Payments", etc.
    product_subcategory: Optional[str] = None
    description: Optional[str] = None
    key_features: Optional[str] = None  # JSON array as string
    target_segment: Optional[str] = None  # "SMB", "Mid-Market", "Enterprise"
    is_primary_product: bool = False
    market_position: Optional[str] = None  # "Leader", "Challenger", "Niche"


class ProductResponse(BaseModel):
    id: int
    competitor_id: int
    product_name: str
    product_category: str
    product_subcategory: Optional[str]
    description: Optional[str]
    key_features: Optional[str]
    target_segment: Optional[str]
    is_primary_product: bool
    market_position: Optional[str]
    launched_date: Optional[datetime]
    last_updated: Optional[datetime]
    pricing_tiers: List[dict] = []

    class Config:
        from_attributes = True


class PricingTierCreate(BaseModel):
    """Create a pricing tier for a product."""
    product_id: int
    tier_name: str  # "Basic", "Professional", "Enterprise"
    tier_position: Optional[int] = None
    pricing_model: str  # "per_visit", "per_provider", "subscription", "percentage_collections", "custom"
    base_price: Optional[float] = None
    price_currency: str = "USD"
    price_unit: Optional[str] = None  # "visit", "provider/month", "location/month"
    price_display: Optional[str] = None  # Original display: "$3.00/visit"
    percentage_rate: Optional[float] = None  # For RCM: 4.5 for 4.5%
    percentage_basis: Optional[str] = None  # "collections", "charges"
    min_volume: Optional[str] = None
    max_volume: Optional[str] = None
    included_features: Optional[str] = None  # JSON array
    excluded_features: Optional[str] = None
    contract_length: Optional[str] = None  # "Monthly", "Annual"
    setup_fee: Optional[float] = None
    implementation_cost: Optional[str] = None
    price_source: Optional[str] = None  # "website", "sales_quote", "customer_intel"


class PricingTierResponse(BaseModel):
    id: int
    product_id: int
    tier_name: str
    tier_position: Optional[int]
    pricing_model: str
    base_price: Optional[float]
    price_currency: str
    price_unit: Optional[str]
    price_display: Optional[str]
    percentage_rate: Optional[float]
    percentage_basis: Optional[str]
    min_volume: Optional[str]
    max_volume: Optional[str]
    contract_length: Optional[str]
    setup_fee: Optional[float]
    implementation_cost: Optional[str]
    price_verified: bool
    price_source: Optional[str]
    confidence_score: Optional[int]
    last_verified: Optional[datetime]

    class Config:
        from_attributes = True


class FeatureMatrixCreate(BaseModel):
    """Create a feature entry for a product."""
    product_id: int
    feature_category: str  # "Patient Intake", "Payments", "Integration"
    feature_name: str  # "Digital Check-In", "Apple Pay Support"
    feature_status: str  # "included", "add_on", "not_available", "coming_soon"
    feature_tier: Optional[str] = None  # Which tier includes this
    notes: Optional[str] = None
    source_url: Optional[str] = None


class CustomerCountCreate(BaseModel):
    """Create a customer count estimate for a competitor."""
    competitor_id: int
    count_value: Optional[int] = None  # Numeric: 3000
    count_display: str  # Display: "3,000+" or "3,000-5,000"
    count_type: str = "estimate"  # "exact", "minimum", "range", "estimate"
    count_unit: str  # "healthcare_organizations", "providers", "locations", "users", "lives_covered"
    count_definition: Optional[str] = None  # "Number of distinct hospital/clinic customers"
    segment_breakdown: Optional[str] = None  # JSON: {"hospitals": 500, "ambulatory": 2500}
    primary_source: str  # "website", "sec_10k", "press_release"
    primary_source_url: Optional[str] = None
    primary_source_date: Optional[datetime] = None
    as_of_date: Optional[datetime] = None  # When this count was valid


class CustomerCountResponse(BaseModel):
    id: int
    competitor_id: int
    count_value: Optional[int]
    count_display: Optional[str]
    count_type: Optional[str]
    count_unit: Optional[str]
    count_definition: Optional[str]
    segment_breakdown: Optional[str]
    is_verified: bool
    verification_method: Optional[str]
    verification_date: Optional[datetime]
    primary_source: Optional[str]
    primary_source_url: Optional[str]
    primary_source_date: Optional[datetime]
    all_sources: Optional[str]
    source_agreement_score: Optional[float]
    confidence_score: Optional[int]
    confidence_level: Optional[str]
    confidence_notes: Optional[str]
    as_of_date: Optional[datetime]
    previous_count: Optional[int]
    growth_rate: Optional[float]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CustomerCountVerifyRequest(BaseModel):
    """Request to verify a customer count with additional sources."""
    verification_method: str  # "sec_filing", "triangulation", "sales_intel", "manual"
    verification_notes: Optional[str] = None
    additional_sources: Optional[List[dict]] = None  # List of {source_type, source_url, value}
