"""Initial schema capture for Certify Intel v6.1.1

Revision ID: 0001
Revises:
Create Date: 2026-01-28

REL-009: This migration captures the current database schema state.
All existing tables and indexes are documented here as the baseline.

Note: This is a "stamp" migration - it doesn't actually create tables
since they already exist. It establishes the starting point for future migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Initial schema - this is a stamp migration.

    The following tables exist in the Certify Intel database:

    Core Tables:
    - competitors: Main competitor entity (65+ fields)
    - competitor_products: Product-level tracking
    - product_pricing_tiers: Tiered pricing models
    - product_feature_matrix: Feature comparison
    - customer_count_estimates: Customer count verification

    Change Tracking:
    - change_logs: Legacy change tracking
    - data_change_history: Enhanced change tracking with reasons
    - activity_logs: User activity audit trail
    - data_sources: Data provenance & confidence scoring
    - refresh_sessions: Scrape session history

    Users & Auth:
    - users: User accounts with roles
    - user_settings: Per-user preferences
    - user_saved_prompts: Saved AI prompts
    - system_prompts: System-level AI prompts

    Sales & Marketing:
    - competitor_dimension_history: Dimension score history
    - battlecards: Generated sales battlecards
    - talking_points: Sales talking points
    - dimension_news_tags: News tagged by dimension
    - competitor_subscriptions: Alert subscriptions
    - win_loss_deals: Competitive deal tracking

    Intelligence:
    - knowledge_base_items: Internal knowledge base
    - news_article_cache: Cached news articles
    - webhook_configs: Webhook integrations
    - alert_rules: Notification rules

    This migration serves as documentation and baseline.
    No actual DDL is executed since tables already exist.
    """
    pass


def downgrade() -> None:
    """
    Downgrade not applicable for initial schema stamp.
    """
    pass
