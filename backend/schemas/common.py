"""
Certify Intel - Common/Misc Pydantic Schemas
"""

from typing import Optional
from pydantic import BaseModel


class DataChangeSubmission(BaseModel):
    competitor_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None
    value_type: str = "text"


class WinLossCreate(BaseModel):
    """FEAT-003: Enhanced win/loss deal model."""
    competitor_id: Optional[int] = None
    competitor_name: str
    outcome: str  # "win" or "loss"
    deal_value: Optional[float] = None
    deal_date: Optional[str] = None
    customer_name: Optional[str] = None
    customer_size: Optional[str] = None
    reason: Optional[str] = None
    sales_rep: Optional[str] = None
    notes: Optional[str] = None
    key_dimension: Optional[str] = None


class WebhookCreate(BaseModel):
    name: str
    url: str
    event_types: str


class SubscriptionCreate(BaseModel):
    competitor_id: int
    notify_email: bool = True
    notify_slack: bool = False
    notify_teams: bool = False
    notify_push: bool = False
    alert_on_pricing: bool = True
    alert_on_products: bool = True
    alert_on_news: bool = True
    alert_on_threat_change: bool = True
    min_severity: str = "Low"


class SubscriptionUpdate(BaseModel):
    notify_email: Optional[bool] = None
    notify_slack: Optional[bool] = None
    notify_teams: Optional[bool] = None
    notify_push: Optional[bool] = None
    alert_on_pricing: Optional[bool] = None
    alert_on_products: Optional[bool] = None
    alert_on_news: Optional[bool] = None
    alert_on_threat_change: Optional[bool] = None
    min_severity: Optional[str] = None


class WebVitalsMetric(BaseModel):
    name: str
    value: float
    rating: Optional[str] = None
    url: Optional[str] = None
