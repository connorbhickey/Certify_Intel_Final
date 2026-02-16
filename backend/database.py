"""
Certify Intel v7.0 - Database Module with SQLAlchemy 2.0 Async Support

Supports both:
- Sync SQLite (for desktop app / PyInstaller bundles)
- Async PostgreSQL (for v7.0 production with pgvector)

Migration Status (February 2026):
==================================
INFRASTRUCTURE: ✅ COMPLETE
- Async engine (create_async_engine)
- Async session maker (async_sessionmaker)
- get_async_db() FastAPI dependency
- get_async_session() context manager
- 20+ async CRUD helper functions

ENDPOINT MIGRATION: ⏳ HYBRID APPROACH
- main.py endpoints: SYNC (237 db.query() calls)
- Agent modules: Can use async helpers directly
- Reason: Full migration is high-risk with 237 queries
- Strategy: Gradually migrate high-impact endpoints as needed

USAGE:
------
Sync (existing endpoints):
    from database import get_db, SessionLocal
    @app.get("/items")
    def get_items(db: Session = Depends(get_db)):
        return db.query(Item).all()

Async (new code / agents):
    from database import get_async_db, get_competitor_by_id
    @app.get("/items/{id}")
    async def get_item(id: int, db: AsyncSession = Depends(get_async_db)):
        return await get_competitor_by_id(db, id)

Helper functions (async):
    from database import get_active_competitors, get_news_articles
    async with get_async_session() as session:
        competitors = await get_active_competitors(session)
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Index, event, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional
import os
import sys
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE URL CONFIGURATION
# =============================================================================

def _get_database_url() -> str:
    """Get sync database URL with PyInstaller awareness."""
    # First check if explicitly set (by __main__.py or user)
    url = os.getenv("DATABASE_URL")
    if url:
        # Convert async URL to sync if needed
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://")
        return url

    # If running as PyInstaller bundle, use exe directory
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        db_path = os.path.join(exe_dir, 'certify_intel.db')
        return f'sqlite:///{db_path}'

    # Default for development (SQLite)
    return "sqlite:///./certify_intel.db"


def _get_async_database_url() -> Optional[str]:
    """
    Get async database URL for PostgreSQL.

    Returns None if using SQLite (not async-compatible without aiosqlite).
    """
    # Check for explicit async URL
    async_url = os.getenv("DATABASE_URL_ASYNC")
    if async_url:
        return async_url

    # Check for regular PostgreSQL URL and convert to async
    url = os.getenv("DATABASE_URL")
    if url and url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")

    # Check for SQLite and use aiosqlite
    if url and url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")

    # Default: Use aiosqlite for development SQLite
    return "sqlite+aiosqlite:///./certify_intel.db"


# =============================================================================
# SYNC ENGINE (Backward Compatible - Desktop App, Alembic)
# =============================================================================

DATABASE_URL = _get_database_url()

# Create sync engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,  # Verify connections before checkout (PERF-012)
        echo=os.getenv("DB_ECHO", "false").lower() == "true"
    )
else:
    # PostgreSQL settings
    engine = create_engine(
        DATABASE_URL,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
        pool_pre_ping=True,  # Verify connections before checkout
        echo=os.getenv("DB_ECHO", "false").lower() == "true"
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =============================================================================
# ASYNC ENGINE (v7.0 Production - PostgreSQL + pgvector)
# =============================================================================

ASYNC_DATABASE_URL = _get_async_database_url()

# Create async engine if URL is available
async_engine = None
AsyncSessionLocal = None

if ASYNC_DATABASE_URL:
    if ASYNC_DATABASE_URL.startswith("sqlite+aiosqlite"):
        # SQLite async engine (for development)
        async_engine = create_async_engine(
            ASYNC_DATABASE_URL,
            echo=os.getenv("DB_ECHO", "false").lower() == "true"
        )
    else:
        # PostgreSQL async engine (for production)
        async_engine = create_async_engine(
            ASYNC_DATABASE_URL,
            pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            pool_pre_ping=True,  # Verify connections before checkout
            echo=os.getenv("DB_ECHO", "false").lower() == "true"
        )

    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    logger.info(f"Async database engine initialized: {ASYNC_DATABASE_URL[:30]}...")


# =============================================================================
# SESSION DEPENDENCY FUNCTIONS
# =============================================================================

def get_db():
    """
    Sync database session dependency (FastAPI).

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async database session dependency (FastAPI).

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Async database not configured. Set DATABASE_URL_ASYNC in .env")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions outside of FastAPI.

    Usage:
        async with get_async_session() as session:
            result = await session.execute(select(Item))
            items = result.scalars().all()
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Async database not configured. Set DATABASE_URL_ASYNC in .env")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# ============== Database Models ==============

class Competitor(Base):
    __tablename__ = "competitors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    website = Column(String)
    status = Column(String, default="Active")


    threat_level = Column(String, default="Medium")
    last_updated = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    data_quality_score = Column(Integer, nullable=True)
    
    # Pricing
    pricing_model = Column(String, nullable=True)
    base_price = Column(String, nullable=True)
    price_unit = Column(String, nullable=True)
    
    # Product
    product_categories = Column(String, nullable=True)
    key_features = Column(Text, nullable=True)
    integration_partners = Column(String, nullable=True)
    certifications = Column(String, nullable=True)
    
    # Market
    target_segments = Column(String, nullable=True)
    customer_size_focus = Column(String, nullable=True)
    geographic_focus = Column(String, nullable=True)
    customer_count = Column(String, nullable=True)
    customer_acquisition_rate = Column(String, nullable=True)
    key_customers = Column(String, nullable=True)
    g2_rating = Column(String, nullable=True)
    
    # Company
    employee_count = Column(String, nullable=True)
    employee_growth_rate = Column(String, nullable=True)
    year_founded = Column(String, nullable=True)
    headquarters = Column(String, nullable=True)
    funding_total = Column(String, nullable=True)
    latest_round = Column(String, nullable=True)
    pe_vc_backers = Column(String, nullable=True)
    
    # Digital
    website_traffic = Column(String, nullable=True)
    social_following = Column(String, nullable=True)
    recent_launches = Column(String, nullable=True)
    news_mentions = Column(String, nullable=True)
    
    # Stock info (for public companies)
    is_public = Column(Boolean, default=False)
    ticker_symbol = Column(String, nullable=True)
    stock_exchange = Column(String, nullable=True)
    
    # Market Vertical Tracking (aligned with Certify Health's 11 markets)
    primary_market = Column(String, nullable=True)  # hospitals, ambulatory, behavioral, etc.
    markets_served = Column(String, nullable=True)  # Semicolon-separated: "hospitals;ambulatory;telehealth"
    market_focus_score = Column(Integer, nullable=True)  # 0-100 overlap with Certify markets
    
    # Product Overlap Tracking (aligned with Certify Health's 7 products)
    has_pxp = Column(Boolean, default=False)  # Patient Experience Platform
    has_pms = Column(Boolean, default=False)  # Practice Management System
    has_rcm = Column(Boolean, default=False)  # Revenue Cycle Management
    has_patient_mgmt = Column(Boolean, default=False)  # Patient Management / EHR
    has_payments = Column(Boolean, default=False)  # CERTIFY Pay equivalent
    has_biometric = Column(Boolean, default=False)  # FaceCheck equivalent
    has_interoperability = Column(Boolean, default=False)  # EHR integrations
    product_overlap_score = Column(Integer, nullable=True)  # 0-100 overlap with Certify products
    
    # Enhanced Analytics Fields
    telehealth_capabilities = Column(Boolean, default=False)
    ai_features = Column(String, nullable=True)  # "ai scribe;chatbot;analytics"
    mobile_app_available = Column(Boolean, default=False)
    hipaa_compliant = Column(Boolean, default=True)
    ehr_integrations = Column(String, nullable=True)  # "Epic;Cerner;Athena"

    # ===========================================
    # SALES & MARKETING MODULE: 9 COMPETITIVE DIMENSIONS (v5.0.7)
    # ===========================================
    # Each dimension has: score (1-5), evidence (text), updated (datetime)

    # Dimension 1: Product Modules & Packaging
    dim_product_packaging_score = Column(Integer, nullable=True)  # 1-5 (1=Major Weakness, 5=Major Strength)
    dim_product_packaging_evidence = Column(Text, nullable=True)
    dim_product_packaging_updated = Column(DateTime, nullable=True)

    # Dimension 2: Interoperability & Integration Depth
    dim_integration_depth_score = Column(Integer, nullable=True)  # 1-5
    dim_integration_depth_evidence = Column(Text, nullable=True)
    dim_integration_depth_updated = Column(DateTime, nullable=True)

    # Dimension 3: Customer Support & Service Model
    dim_support_service_score = Column(Integer, nullable=True)  # 1-5
    dim_support_service_evidence = Column(Text, nullable=True)
    dim_support_service_updated = Column(DateTime, nullable=True)

    # Dimension 4: Retention & Product Stickiness
    dim_retention_stickiness_score = Column(Integer, nullable=True)  # 1-5
    dim_retention_stickiness_evidence = Column(Text, nullable=True)
    dim_retention_stickiness_updated = Column(DateTime, nullable=True)

    # Dimension 5: User Adoption & Ease of Use
    dim_user_adoption_score = Column(Integer, nullable=True)  # 1-5
    dim_user_adoption_evidence = Column(Text, nullable=True)
    dim_user_adoption_updated = Column(DateTime, nullable=True)

    # Dimension 6: Implementation Effort & Time to Value
    dim_implementation_ttv_score = Column(Integer, nullable=True)  # 1-5
    dim_implementation_ttv_evidence = Column(Text, nullable=True)
    dim_implementation_ttv_updated = Column(DateTime, nullable=True)

    # Dimension 7: Reliability & Enterprise Readiness
    dim_reliability_enterprise_score = Column(Integer, nullable=True)  # 1-5
    dim_reliability_enterprise_evidence = Column(Text, nullable=True)
    dim_reliability_enterprise_updated = Column(DateTime, nullable=True)

    # Dimension 8: Pricing Model & Commercial Flexibility
    dim_pricing_flexibility_score = Column(Integer, nullable=True)  # 1-5
    dim_pricing_flexibility_evidence = Column(Text, nullable=True)
    dim_pricing_flexibility_updated = Column(DateTime, nullable=True)

    # Dimension 9: Reporting & Analytics Capability
    dim_reporting_analytics_score = Column(Integer, nullable=True)  # 1-5
    dim_reporting_analytics_evidence = Column(Text, nullable=True)
    dim_reporting_analytics_updated = Column(DateTime, nullable=True)

    # Aggregate Dimension Scores
    dim_overall_score = Column(Float, nullable=True)  # Average of all 9 dimensions
    dim_sales_priority = Column(String, nullable=True)  # High/Medium/Low based on threat + dimensions

    # ===========================================
    # FREE API DATA SOURCES
    # ===========================================
    
    # Clearbit Logo API (free unlimited)
    logo_url = Column(String, nullable=True)  # https://logo.clearbit.com/domain.com
    
    # SEC EDGAR API (free unlimited - public companies only)
    sec_cik = Column(String, nullable=True)  # SEC Central Index Key
    annual_revenue = Column(String, nullable=True)  # From 10-K filing
    net_income = Column(String, nullable=True)  # From 10-K filing
    sec_employee_count = Column(String, nullable=True)  # From 10-K filing
    fiscal_year_end = Column(String, nullable=True)  # e.g., "January 31"
    recent_sec_filings = Column(String, nullable=True)  # JSON: recent 8-K, 10-Q filings
    sec_risk_factors = Column(String, nullable=True)  # Competition section from 10-K
    
    # Hunter.io API (free 25/month)
    email_pattern = Column(String, nullable=True)  # "{first}.{last}@company.com"
    key_contacts = Column(String, nullable=True)  # JSON: executive emails
    hunter_email_count = Column(Integer, nullable=True)  # Total emails found
    
    # Google Custom Search API (free 100/day)
    last_google_search = Column(DateTime, nullable=True)  # Rate limiting

    # ===========================================
    # EXTENDED DATA FIELDS (v6.1.2) - 50 NEW FIELDS
    # ===========================================

    # --- SOCIAL MEDIA METRICS (8 fields) ---
    linkedin_followers = Column(Integer, nullable=True)  # LinkedIn company page followers
    linkedin_employees = Column(Integer, nullable=True)  # LinkedIn employee count
    linkedin_url = Column(String, nullable=True)  # LinkedIn company URL
    twitter_followers = Column(Integer, nullable=True)  # Twitter/X followers
    twitter_handle = Column(String, nullable=True)  # @handle
    facebook_followers = Column(Integer, nullable=True)  # Facebook page likes/followers
    instagram_followers = Column(Integer, nullable=True)  # Instagram followers
    youtube_subscribers = Column(Integer, nullable=True)  # YouTube channel subscribers

    # --- FINANCIAL METRICS (10 fields) ---
    estimated_revenue = Column(String, nullable=True)  # e.g., "$50M-100M"
    revenue_growth_rate = Column(String, nullable=True)  # e.g., "25% YoY"
    profit_margin = Column(String, nullable=True)  # e.g., "15%"
    estimated_valuation = Column(String, nullable=True)  # e.g., "$500M"
    burn_rate = Column(String, nullable=True)  # Monthly burn rate for startups
    runway_months = Column(Integer, nullable=True)  # Estimated runway
    last_funding_date = Column(DateTime, nullable=True)  # Date of last funding round
    funding_stage = Column(String, nullable=True)  # Seed, Series A, B, C, IPO, etc.
    debt_financing = Column(String, nullable=True)  # Any debt/credit facilities
    revenue_per_employee = Column(String, nullable=True)  # Revenue efficiency metric

    # --- LEADERSHIP & TEAM (8 fields) ---
    ceo_name = Column(String, nullable=True)  # CEO name
    ceo_linkedin = Column(String, nullable=True)  # CEO LinkedIn URL
    cto_name = Column(String, nullable=True)  # CTO/CPO name
    cfo_name = Column(String, nullable=True)  # CFO name
    executive_changes = Column(Text, nullable=True)  # Recent executive departures/hires
    board_members = Column(Text, nullable=True)  # Key board members
    advisors = Column(Text, nullable=True)  # Notable advisors
    founder_background = Column(Text, nullable=True)  # Founder previous companies/experience

    # --- EMPLOYEE & CULTURE (6 fields) ---
    glassdoor_rating = Column(Float, nullable=True)  # Glassdoor overall rating (1-5)
    glassdoor_reviews_count = Column(Integer, nullable=True)  # Number of reviews
    glassdoor_recommend_pct = Column(Integer, nullable=True)  # % who recommend
    indeed_rating = Column(Float, nullable=True)  # Indeed rating
    employee_turnover_rate = Column(String, nullable=True)  # Estimated turnover
    hiring_velocity = Column(Integer, nullable=True)  # Open positions count

    # --- PRODUCT & TECHNOLOGY (8 fields) ---
    product_count = Column(Integer, nullable=True)  # Number of distinct products
    latest_product_launch = Column(String, nullable=True)  # Most recent product launch
    tech_stack = Column(Text, nullable=True)  # Known technologies used
    cloud_provider = Column(String, nullable=True)  # AWS, Azure, GCP, etc.
    api_available = Column(Boolean, default=False)  # Public API availability
    api_documentation_url = Column(String, nullable=True)  # API docs link
    open_source_contributions = Column(Boolean, default=False)  # GitHub activity
    rd_investment_pct = Column(String, nullable=True)  # R&D as % of revenue

    # --- MARKET & COMPETITIVE (6 fields) ---
    estimated_market_share = Column(String, nullable=True)  # e.g., "5-8%"
    nps_score = Column(Integer, nullable=True)  # Net Promoter Score (-100 to 100)
    customer_churn_rate = Column(String, nullable=True)  # Annual churn rate
    average_contract_value = Column(String, nullable=True)  # ACV
    sales_cycle_length = Column(String, nullable=True)  # Typical sales cycle
    competitive_win_rate = Column(String, nullable=True)  # Win rate vs Certify

    # --- REGULATORY & COMPLIANCE (4 fields) ---
    soc2_certified = Column(Boolean, default=False)  # SOC 2 Type II
    hitrust_certified = Column(Boolean, default=False)  # HITRUST CSF
    iso27001_certified = Column(Boolean, default=False)  # ISO 27001
    legal_issues = Column(Text, nullable=True)  # Known lawsuits, regulatory issues

    # --- PATENTS & IP (4 fields) ---
    patent_count = Column(Integer, nullable=True)  # Total patents filed/granted
    recent_patents = Column(Text, nullable=True)  # Recent patent filings (JSON)
    trademark_count = Column(Integer, nullable=True)  # Registered trademarks
    ip_litigation = Column(Text, nullable=True)  # IP-related legal matters

    # --- PARTNERSHIPS & ECOSYSTEM (4 fields) ---
    strategic_partners = Column(Text, nullable=True)  # Key partnerships
    reseller_partners = Column(Text, nullable=True)  # Channel/reseller partners
    marketplace_presence = Column(Text, nullable=True)  # App stores, marketplaces
    acquisition_history = Column(Text, nullable=True)  # Companies acquired

    # --- CUSTOMER INTELLIGENCE (2 fields) ---
    notable_customer_wins = Column(Text, nullable=True)  # Recent big customer wins
    customer_case_studies = Column(Text, nullable=True)  # URLs to case studies

    # Metadata
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_verified_at = Column(DateTime, nullable=True)  # For freshness tracking
    extended_data_updated = Column(DateTime, nullable=True)  # When extended fields were last updated
    ai_threat_summary = Column(Text, nullable=True)  # AI-generated 2-4 sentence threat summary for battlecard


class ChangeLog(Base):
    __tablename__ = "change_log"
    
    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, index=True)
    competitor_name = Column(String)
    change_type = Column(String)
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    source = Column(String, nullable=True)
    severity = Column(String, default="Low")
    detected_at = Column(DateTime, default=datetime.utcnow)


class DataSource(Base):
    """Enhanced source tracking for every data point with confidence scoring."""
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    field_name = Column(String, index=True)  # e.g., "customer_count", "base_price"

    # Value tracking
    current_value = Column(String, nullable=True)
    previous_value = Column(String, nullable=True)

    # Source attribution
    source_type = Column(String)  # "website_scrape", "sec_filing", "manual", "api", "news"
    source_url = Column(String, nullable=True)
    source_name = Column(String, nullable=True)  # "Company Website", "SEC 10-K 2025", "KLAS Report"
    extraction_method = Column(String, nullable=True)  # "gpt_extraction", "structured_api", "manual_entry"
    extracted_at = Column(DateTime, default=datetime.utcnow)

    # Confidence scoring (Admiralty Code)
    source_reliability = Column(String, nullable=True)  # A-F scale (A=completely reliable, F=unknown)
    information_credibility = Column(Integer, nullable=True)  # 1-6 scale (1=confirmed, 6=cannot be judged)
    confidence_score = Column(Integer, nullable=True)  # 0-100 composite score
    confidence_level = Column(String, nullable=True)  # "high", "moderate", "low"

    # Verification tracking
    is_verified = Column(Boolean, default=False)
    verified_by = Column(String, nullable=True)  # "triangulation", "manual", "sec_filing"
    verification_date = Column(DateTime, nullable=True)
    corroborating_sources = Column(Integer, default=0)  # Number of sources that agree

    # Temporal relevance
    data_as_of_date = Column(DateTime, nullable=True)  # When the data was true (not when extracted)
    staleness_days = Column(Integer, default=0)

    # Legacy fields for backwards compatibility
    entered_by = Column(String, nullable=True)  # Username for manual entries
    formula = Column(Text, nullable=True)  # Formula string for calculated values
    verified_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # v7.1 Enhancement: KB reconciliation link
    kb_document_id = Column(String(36), nullable=True)  # Link to knowledge_documents (pgvector)
    kb_item_id = Column(Integer, nullable=True)  # Link to knowledge_base table
    kb_chunk_id = Column(Integer, nullable=True)  # Specific chunk if applicable
    kb_extraction_id = Column(Integer, nullable=True)  # Link to kb_data_extractions
    reconciliation_status = Column(String, nullable=True)  # kb_only, live_only, merged, conflict
    conflict_details = Column(Text, nullable=True)  # JSON: what conflicts exist

    # v8.3.0: Source URL refinement tracking
    source_page_url = Column(String, nullable=True)      # Exact page URL (not homepage)
    source_anchor_text = Column(String, nullable=True)    # Text fragment for highlighting
    source_css_selector = Column(String, nullable=True)   # CSS selector path to element
    source_section = Column(String, nullable=True)        # Page section (e.g., "Pricing", "About")
    deep_link_url = Column(String, nullable=True)         # Full URL with #:~:text= fragment
    last_url_verified = Column(DateTime, nullable=True)   # When URL was last checked
    url_status = Column(String, default="pending")        # pending/verified/broken/redirected


class CompetitorProduct(Base):
    """Individual product/solution offered by a competitor."""
    __tablename__ = "competitor_products"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)

    # Product identification
    product_name = Column(String)  # e.g., "Phreesia Intake", "Athena Collector"
    product_category = Column(String)  # e.g., "Patient Intake", "RCM", "EHR"
    product_subcategory = Column(String, nullable=True)  # e.g., "Self-Service Kiosk"

    # Product details
    description = Column(Text, nullable=True)
    key_features = Column(Text, nullable=True)  # JSON array
    target_segment = Column(String, nullable=True)  # "SMB", "Mid-Market", "Enterprise"

    # Competitive positioning
    is_primary_product = Column(Boolean, default=False)  # Main revenue driver
    market_position = Column(String, nullable=True)  # "Leader", "Challenger", "Niche"

    # Metadata
    launched_date = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)

    # Relationships
    pricing_tiers = relationship("ProductPricingTier", back_populates="product")
    created_at = Column(DateTime, default=datetime.utcnow)


class ProductPricingTier(Base):
    """Pricing tier for a specific product."""
    __tablename__ = "product_pricing_tiers"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("competitor_products.id"), index=True)

    # Tier identification
    tier_name = Column(String)  # e.g., "Basic", "Professional", "Enterprise"
    tier_position = Column(Integer, nullable=True)  # 1, 2, 3... for ordering

    # Pricing structure (based on healthcare SaaS models)
    pricing_model = Column(String)  # "per_visit", "per_provider", "per_location", "subscription", "percentage_collections", "custom"

    # Price details
    base_price = Column(Float, nullable=True)  # Numeric value
    price_currency = Column(String, default="USD")
    price_unit = Column(String, nullable=True)  # "visit", "provider/month", "location/month"
    price_display = Column(String, nullable=True)  # Original display: "$3.00/visit", "Contact Sales"

    # For percentage-based pricing (RCM)
    percentage_rate = Column(Float, nullable=True)  # e.g., 4.5 for 4.5%
    percentage_basis = Column(String, nullable=True)  # "collections", "charges", "net_revenue"

    # Tier limitations
    min_volume = Column(String, nullable=True)  # "100 visits/month"
    max_volume = Column(String, nullable=True)  # "Unlimited"
    included_features = Column(Text, nullable=True)  # JSON array
    excluded_features = Column(Text, nullable=True)  # JSON array

    # Contract terms
    contract_length = Column(String, nullable=True)  # "Monthly", "Annual", "3-year"
    setup_fee = Column(Float, nullable=True)
    implementation_cost = Column(String, nullable=True)  # "Included", "$5,000", "Custom"

    # Data quality
    price_verified = Column(Boolean, default=False)
    price_source = Column(String, nullable=True)  # "website", "sales_quote", "customer_intel"
    confidence_score = Column(Integer, nullable=True)
    last_verified = Column(DateTime, nullable=True)

    # Relationships
    product = relationship("CompetitorProduct", back_populates="pricing_tiers")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductFeatureMatrix(Base):
    """Feature comparison matrix across products."""
    __tablename__ = "product_feature_matrix"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("competitor_products.id"), index=True)

    feature_category = Column(String)  # "Patient Intake", "Payments", "Integration"
    feature_name = Column(String)  # "Digital Check-In", "Apple Pay Support"
    feature_status = Column(String)  # "included", "add_on", "not_available", "coming_soon"
    feature_tier = Column(String, nullable=True)  # Which tier includes this

    notes = Column(Text, nullable=True)
    source_url = Column(String, nullable=True)
    last_verified = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CustomerCountEstimate(Base):
    """Detailed customer count tracking with verification."""
    __tablename__ = "customer_count_estimates"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)

    # The estimate
    count_value = Column(Integer, nullable=True)  # Numeric: 3000
    count_display = Column(String, nullable=True)  # Display: "3,000+" or "3,000-5,000"
    count_type = Column(String, nullable=True)  # "exact", "minimum", "range", "estimate"

    # What is being counted (CRITICAL CONTEXT)
    count_unit = Column(String, nullable=True)  # "healthcare_organizations", "providers", "locations", "users", "lives_covered"
    count_definition = Column(Text, nullable=True)  # "Number of distinct hospital/clinic customers"

    # Segment breakdown (if available)
    segment_breakdown = Column(Text, nullable=True)  # JSON: {"hospitals": 500, "ambulatory": 2500}

    # Verification
    is_verified = Column(Boolean, default=False)
    verification_method = Column(String, nullable=True)  # "sec_filing", "triangulation", "sales_intel"
    verification_date = Column(DateTime, nullable=True)

    # Source tracking
    primary_source = Column(String, nullable=True)  # "website", "sec_10k", "press_release"
    primary_source_url = Column(String, nullable=True)
    primary_source_date = Column(DateTime, nullable=True)

    # Multi-source data
    all_sources = Column(Text, nullable=True)  # JSON array of all source claims
    source_agreement_score = Column(Float, nullable=True)  # 0-1, how much sources agree

    # Confidence
    confidence_score = Column(Integer, nullable=True)  # 0-100
    confidence_level = Column(String, nullable=True)  # "high", "moderate", "low"
    confidence_notes = Column(Text, nullable=True)

    # Historical tracking
    as_of_date = Column(DateTime, nullable=True)  # When this count was valid
    previous_count = Column(Integer, nullable=True)
    growth_rate = Column(Float, nullable=True)  # YoY growth %

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataChangeHistory(Base):
    """Detailed audit log of all data changes with user attribution."""
    __tablename__ = "data_change_history"
    
    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, index=True)
    competitor_name = Column(String)
    field_name = Column(String, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String)  # Username who made the change
    change_reason = Column(String, nullable=True)
    source_url = Column(String, nullable=True)  # Where the new data came from
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)


class PendingDataChange(Base):
    """Pending data changes awaiting admin approval."""
    __tablename__ = "pending_data_changes"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, index=True)
    competitor_name = Column(String)
    field_name = Column(String, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    value_type = Column(String, default="text")  # text or number
    source_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    submitted_by = Column(String)  # Username who submitted
    submitted_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String, default="pending")  # pending, approved, rejected
    reviewed_by = Column(String, nullable=True)  # Admin who reviewed
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)


class User(Base):
    """User model for authentication and RBAC."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String, nullable=True)
    role = Column(String, default="viewer")  # viewer, analyst, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String, nullable=True)
    mfa_backup_codes = Column(Text, nullable=True)  # JSON array of hashed codes


class RefreshToken(Base):
    """Refresh tokens for JWT token rotation."""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemPrompt(Base):
    """Dynamic system prompts for AI generation. user_id=NULL means global prompt."""
    __tablename__ = "system_prompts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # NULL = global prompt
    key = Column(String, index=True)  # e.g., "dashboard_summary", "chat_persona"
    category = Column(String, nullable=True, index=True)  # e.g., "dashboard", "battlecards", "news", "discovery", "competitor", "knowledge_base"
    description = Column(String, nullable=True)  # Human-readable label for dropdown display
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeBaseItem(Base):
    """Internal documents and text for RAG."""
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content_text = Column(Text, nullable=False)   # Extracted text from PDF/Doc
    source_type = Column(String, default="manual") # manual, upload, integration
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # v7.1 Enhancement: Document metadata for reconciliation
    content_type = Column(String, nullable=True)  # pdf, docx, txt, md, html
    category = Column(String, nullable=True)  # general, strategy, product, sales, marketing
    tags = Column(Text, nullable=True)  # JSON array of tags
    source = Column(String, nullable=True)  # upload:filename.pdf, discovery, client_provided
    extra_metadata = Column(Text, nullable=True)  # JSON: original_filename, file_size, uploaded_by

    # Temporal tracking for reconciliation
    document_date = Column(DateTime, nullable=True)  # When document was created/published
    data_as_of_date = Column(DateTime, nullable=True)  # User-provided "data valid as of" date
    document_type = Column(String, default="upload")  # upload, discovery, client_provided, scrape

    # Entity linking
    linked_competitor_ids = Column(Text, nullable=True)  # JSON array of auto-linked competitor IDs
    extraction_status = Column(String, default="pending")  # pending, completed, failed
    content_hash = Column(String(64), nullable=True, index=True)  # SHA256 for deduplication


class KBEntityLink(Base):
    """Links KB documents/chunks to competitor entities for data reconciliation."""
    __tablename__ = "kb_entity_links"

    id = Column(Integer, primary_key=True, index=True)

    # Source document reference
    document_id = Column(String(36), nullable=True, index=True)  # Links to knowledge_documents (pgvector)
    kb_item_id = Column(Integer, ForeignKey("knowledge_base.id"), nullable=True, index=True)  # Links to knowledge_base
    chunk_id = Column(Integer, nullable=True)  # Optional: specific chunk

    # Linked entity
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False, index=True)

    # Linking metadata
    link_type = Column(String, default="inferred")  # explicit, inferred, manual
    link_confidence = Column(Float, default=0.0)  # 0.0-1.0
    extracted_entities = Column(Text, nullable=True)  # JSON: names/products found in doc

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    validated_by = Column(String, nullable=True)  # User who validated the link
    validated_at = Column(DateTime, nullable=True)

    # Relationships
    competitor = relationship("Competitor", backref="kb_links")


class KBDataExtraction(Base):
    """Structured data extracted from KB documents for reconciliation with live data."""
    __tablename__ = "kb_data_extractions"

    id = Column(Integer, primary_key=True, index=True)

    # Source document reference
    document_id = Column(String(36), nullable=True, index=True)  # Links to knowledge_documents (pgvector)
    kb_item_id = Column(Integer, ForeignKey("knowledge_base.id"), nullable=True, index=True)
    chunk_id = Column(Integer, nullable=True)

    # Extracted data
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False, index=True)
    field_name = Column(String, nullable=False, index=True)  # customer_count, pricing, employee_count, etc.
    extracted_value = Column(String, nullable=False)  # The actual extracted value
    extraction_context = Column(Text, nullable=True)  # Surrounding text for verification

    # Quality metrics
    extraction_confidence = Column(Float, default=0.0)  # AI confidence 0.0-1.0
    extraction_method = Column(String, default="gpt_extraction")  # gpt_extraction, regex, table_parse

    # Temporal tracking
    data_as_of_date = Column(DateTime, nullable=True)  # When the data was true
    document_date = Column(DateTime, nullable=True)  # Document creation date

    # Reconciliation status
    status = Column(String, default="pending")  # pending, verified, rejected, superseded
    reconciliation_note = Column(Text, nullable=True)  # Why verified/rejected
    verified_by = Column(String, nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # Link to DataSource for reconciliation
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    competitor = relationship("Competitor", backref="kb_extractions")


class SystemSetting(Base):
    __tablename__ = "system_settings"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class WinLossDeal(Base):
    """Record of a competitive deal (win or loss). Each user tracks their own deals."""
    __tablename__ = "win_loss_deals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Owner of this deal record
    competitor_id = Column(Integer, index=True)
    competitor_name = Column(String)
    outcome = Column(String)  # "win" or "loss"
    deal_value = Column(Float, nullable=True)
    deal_date = Column(DateTime, default=datetime.utcnow)
    customer_name = Column(String, nullable=True)
    customer_size = Column(String, nullable=True)
    reason = Column(String, nullable=True)  # "loss_reason" or "win_factor"
    sales_rep = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WebhookConfig(Base):
    """Configuration for outbound webhooks."""
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    url = Column(String)
    event_types = Column(String)  # JSON-encoded list of events or comma-separated
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSettings(Base):
    """Personal settings for each user (notification preferences, schedules, etc.)."""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    setting_key = Column(String, index=True)  # e.g., "notifications", "schedule", "display_preferences"
    setting_value = Column(Text, nullable=False)  # JSON-encoded value
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActivityLog(Base):
    """Logs all user activities including data refreshes, logins, etc. Shared across all users."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user_email = Column(String, index=True)  # Store email for easy display
    action_type = Column(String, index=True)  # "data_refresh", "login", "competitor_update", etc.
    action_details = Column(Text, nullable=True)  # JSON-encoded details
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UserSavedPrompt(Base):
    """User-specific saved prompts for AI generation. Each user can save multiple named prompts."""
    __tablename__ = "user_saved_prompts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)  # User-friendly name for the prompt
    prompt_type = Column(String, default="executive_summary")  # "executive_summary", "chat_persona", etc.
    content = Column(Text, nullable=False)  # The actual prompt content
    is_default = Column(Boolean, default=False)  # If true, this is the user's default for this type
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DiscoveryProfile(Base):
    """Saved discovery qualification profiles for AI-driven competitor discovery."""
    __tablename__ = "discovery_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # NULL = shared profile
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)

    # Industry/Market Segments (JSON array)
    target_segments = Column(Text, nullable=True)  # ["hospital", "ambulatory", "behavioral_health"]

    # Required Product Capabilities (JSON array)
    required_capabilities = Column(Text, nullable=True)  # ["pxp", "rcm", "pms", "telehealth"]

    # Company Size Criteria (JSON object)
    company_size = Column(Text, nullable=True)  # {"min_employees": 50, "max_employees": 5000}

    # Geography (JSON array)
    geography = Column(Text, nullable=True)  # ["us", "canada", "international"]

    # Funding Stage (JSON array)
    funding_stages = Column(Text, nullable=True)  # ["seed", "series_a", "series_b", "profitable"]

    # Technology Requirements (JSON array)
    tech_requirements = Column(Text, nullable=True)  # ["cloud", "mobile", "fhir", "hl7"]

    # Exclusion Criteria (JSON array)
    exclusions = Column(Text, nullable=True)  # ["consulting", "pharma", "medical_devices"]

    # Custom Keywords (JSON object)
    custom_keywords = Column(Text, nullable=True)  # {"include": [...], "exclude": [...]}

    # AI Instructions (free-form supplement)
    ai_instructions = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RefreshSession(Base):
    """Phase 4: Task 5.0.1-031 - Tracks each data refresh session with results for audit trail."""
    __tablename__ = "refresh_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    competitors_scanned = Column(Integer, default=0)
    changes_detected = Column(Integer, default=0)
    new_values_added = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    ai_summary = Column(Text, nullable=True)  # Store the AI-generated summary
    change_details = Column(Text, nullable=True)  # JSON-encoded change details
    status = Column(String, default="in_progress")  # in_progress, completed, failed


# ===========================================
# SALES & MARKETING MODULE TABLES (v5.0.7)
# ===========================================

class CompetitorDimensionHistory(Base):
    """Track dimension score changes over time for audit trail and trend analysis."""
    __tablename__ = "competitor_dimension_history"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    dimension_id = Column(String, index=True)  # e.g., "product_packaging", "integration_depth"
    old_score = Column(Integer, nullable=True)  # Previous score (null if first entry)
    new_score = Column(Integer)  # New score (1-5)
    evidence = Column(Text, nullable=True)  # Supporting evidence for the score change
    source = Column(String, default="manual")  # "manual", "ai", "news", "review"
    confidence = Column(String, nullable=True)  # "low", "medium", "high"
    changed_by = Column(String)  # User email or "system"
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)


class Battlecard(Base):
    """Generated battlecards for competitors - stored for quick retrieval and versioning."""
    __tablename__ = "battlecards"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    title = Column(String)  # e.g., "Epic Systems Full Battlecard"
    content = Column(Text)  # JSON or Markdown content
    battlecard_type = Column(String)  # "full", "quick", "objection_handler"
    focus_dimensions = Column(String, nullable=True)  # JSON array of dimension IDs
    deal_context = Column(Text, nullable=True)  # Optional deal-specific context
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String)  # User email or "ai"
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    pdf_path = Column(String, nullable=True)  # Path to exported PDF
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TalkingPoint(Base):
    """Dimension-specific talking points for sales conversations."""
    __tablename__ = "talking_points"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    dimension_id = Column(String, index=True)  # e.g., "product_packaging"
    point_type = Column(String, index=True)  # "strength", "weakness", "objection", "counter"
    content = Column(Text)  # The talking point text
    context = Column(Text, nullable=True)  # When to use this talking point
    effectiveness_score = Column(Integer, nullable=True)  # From win/loss feedback (1-5)
    usage_count = Column(Integer, default=0)  # How many times this point was used
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)  # User email or "ai"
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class DimensionNewsTag(Base):
    """Link news articles to competitive dimensions for dimension-aware news filtering."""
    __tablename__ = "dimension_news_tags"

    id = Column(Integer, primary_key=True, index=True)
    news_url = Column(String, index=True)  # URL of the news article
    news_title = Column(String)  # Title for display
    news_snippet = Column(Text, nullable=True)  # Brief excerpt
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    dimension_id = Column(String, index=True)  # e.g., "product_packaging"
    relevance_score = Column(Float)  # 0-1 confidence that article relates to dimension
    sentiment = Column(String, nullable=True)  # "positive", "negative", "neutral"
    tagged_at = Column(DateTime, default=datetime.utcnow, index=True)
    tagged_by = Column(String)  # "ai" or user email
    is_validated = Column(Boolean, default=False)  # User validated the tag


# ===========================================
# TEAM FEATURES (v5.2.0)
# ===========================================

class Team(Base):
    """Team model for grouping users and enabling team collaboration."""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Team settings
    default_dashboard_layout = Column(String, default="standard")  # standard, compact, detailed
    notification_settings = Column(Text, nullable=True)  # JSON-encoded team notification preferences


class TeamMembership(Base):
    """Association table linking users to teams with roles."""
    __tablename__ = "team_memberships"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    role = Column(String, default="member")  # owner, admin, member
    joined_at = Column(DateTime, default=datetime.utcnow)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class CompetitorAnnotation(Base):
    """Shared annotations/notes on competitors visible to team members."""
    __tablename__ = "competitor_annotations"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)  # NULL = personal note

    # Annotation content
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    annotation_type = Column(String, default="note")  # note, insight, warning, opportunity, action_item
    priority = Column(String, default="normal")  # low, normal, high, critical

    # Visibility
    is_public = Column(Boolean, default=True)  # Visible to all team members
    is_pinned = Column(Boolean, default=False)  # Pinned to top of annotations

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Context (optional - link to specific field or dimension)
    field_name = Column(String, nullable=True)  # e.g., "pricing", "customer_count"
    dimension_id = Column(String, nullable=True)  # e.g., "product_packaging"


class AnnotationReply(Base):
    """Replies to annotations for threaded discussions."""
    __tablename__ = "annotation_replies"

    id = Column(Integer, primary_key=True, index=True)
    annotation_id = Column(Integer, ForeignKey("competitor_annotations.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DashboardConfiguration(Base):
    """Role-based dashboard configurations and user customizations."""
    __tablename__ = "dashboard_configurations"

    id = Column(Integer, primary_key=True, index=True)
    config_type = Column(String, index=True)  # "role", "user", "team"
    config_key = Column(String, index=True)  # role name, user_id, or team_id

    # Layout settings
    layout = Column(String, default="standard")  # standard, compact, detailed, custom
    widgets = Column(Text, nullable=True)  # JSON: enabled widgets and their positions

    # Display preferences
    default_threat_filter = Column(String, nullable=True)  # "all", "high", "medium", "low"
    default_sort = Column(String, default="threat_level")
    items_per_page = Column(Integer, default=10)

    # Feature visibility (role-based permissions)
    can_view_analytics = Column(Boolean, default=True)
    can_view_financials = Column(Boolean, default=True)
    can_edit_competitors = Column(Boolean, default=False)
    can_manage_users = Column(Boolean, default=False)
    can_export_data = Column(Boolean, default=True)
    can_trigger_refresh = Column(Boolean, default=False)

    # Quick access
    pinned_competitors = Column(Text, nullable=True)  # JSON array of competitor IDs
    favorite_reports = Column(Text, nullable=True)  # JSON array of report configurations

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TeamActivity(Base):
    """Track team-level activities for collaboration awareness."""
    __tablename__ = "team_activities"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    user_email = Column(String)
    activity_type = Column(String, index=True)  # "annotation", "update", "export", "insight"
    activity_details = Column(Text, nullable=True)  # JSON details
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class NewsArticleCache(Base):
    """
    Cache for fetched news articles (v5.0.8).

    Stores news articles to reduce API calls and improve load times.
    Articles are automatically refreshed by the background scheduler.
    """
    __tablename__ = "news_article_cache"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    competitor_name = Column(String, index=True)

    # Article data
    title = Column(String)
    url = Column(String, index=True)  # Dedupe key
    source = Column(String)  # e.g., "TechCrunch", "Reuters"
    source_type = Column(String)  # google_news, sec_edgar, gnews, mediastack, newsdata
    published_at = Column(DateTime, index=True)
    snippet = Column(Text, nullable=True)

    # Analysis
    sentiment = Column(String)  # positive, neutral, negative
    event_type = Column(String, nullable=True)  # funding, acquisition, product_launch, partnership, leadership
    is_major_event = Column(Boolean, default=False)

    # Dimension tags (v5.0.8)
    dimension_tags = Column(Text, nullable=True)  # JSON: [{"dimension": "pricing_flexibility", "confidence": 0.8}]

    # Metadata
    fetched_at = Column(DateTime, default=datetime.utcnow)
    cache_expires_at = Column(DateTime, index=True)  # Auto-refresh after this time
    is_archived = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class PersistentCache(Base):
    """
    Generic key-value cache persisted to SQLite (v8.0.8).

    Stores JSON blobs that survive server restarts: discovery results,
    dashboard summaries, and other ephemeral AI outputs.
    """
    __tablename__ = "persistent_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, unique=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    data_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# SM-011: Competitor Alert Subscriptions
class ChatSession(Base):
    """Persistent chat sessions tied to a user and page context."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    page_context = Column(String, index=True)  # "dashboard", "battlecard_123", "news", "analytics_swot_45"
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=True)
    title = Column(String, nullable=True)  # Auto-generated from first message
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)  # False = user cleared

    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    """Individual message within a chat session."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), index=True)
    role = Column(String)  # "user", "assistant", "system"
    content = Column(Text)
    metadata_json = Column(Text, nullable=True)  # JSON: model, tokens, latency, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class CompetitorSubscription(Base):
    """User subscriptions to competitor alerts for instant notifications."""
    __tablename__ = "competitor_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)

    # Notification preferences
    notify_email = Column(Boolean, default=True)
    notify_slack = Column(Boolean, default=False)
    notify_teams = Column(Boolean, default=False)
    notify_push = Column(Boolean, default=False)

    # Alert filters
    alert_on_pricing = Column(Boolean, default=True)
    alert_on_products = Column(Boolean, default=True)
    alert_on_news = Column(Boolean, default=True)
    alert_on_threat_change = Column(Boolean, default=True)
    min_severity = Column(String, default="Low")  # Low, Medium, High

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_notified_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", backref="subscriptions")
    competitor = relationship("Competitor", backref="subscriptions")


class CompetitorRelationship(Base):
    """Tracks relationships between competitors (parent/subsidiary/partner/competitor)."""
    __tablename__ = "competitor_relationships"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False, index=True)
    related_id = Column(Integer, ForeignKey("competitors.id"), nullable=False, index=True)
    relationship_type = Column(String, nullable=False)  # parent, subsidiary, partner, competitor
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)  # user email


# ===========================================
# PERF-005: Database Performance Optimization
# ===========================================

# Composite indexes for common query patterns
Index('ix_competitor_threat_status', Competitor.threat_level, Competitor.status)
Index('ix_competitor_primary_market', Competitor.primary_market, Competitor.threat_level)
Index('ix_changelog_competitor_detected', ChangeLog.competitor_id, ChangeLog.detected_at.desc())
Index('ix_datasource_competitor_field', DataSource.competitor_id, DataSource.field_name)
Index('ix_datasource_confidence', DataSource.confidence_score, DataSource.is_verified)
Index('ix_product_competitor_category', CompetitorProduct.competitor_id, CompetitorProduct.product_category)
Index('ix_product_market_position', CompetitorProduct.market_position, CompetitorProduct.is_primary_product)
Index('ix_pricing_product_tier', ProductPricingTier.product_id, ProductPricingTier.tier_position)
Index('ix_feature_product_category', ProductFeatureMatrix.product_id, ProductFeatureMatrix.feature_category)
Index('ix_history_competitor_field', DataChangeHistory.competitor_id, DataChangeHistory.field_name)
Index('ix_history_changed_at', DataChangeHistory.changed_at.desc())
Index('ix_activity_user_type', ActivityLog.user_id, ActivityLog.action_type)
Index('ix_activity_created_desc', ActivityLog.created_at.desc())
Index('ix_winloss_user_outcome', WinLossDeal.user_id, WinLossDeal.outcome)
Index('ix_winloss_competitor_date', WinLossDeal.competitor_id, WinLossDeal.deal_date.desc())
Index('ix_dimension_history_competitor_dim', CompetitorDimensionHistory.competitor_id, CompetitorDimensionHistory.dimension_id)
Index('ix_battlecard_competitor_type', Battlecard.competitor_id, Battlecard.battlecard_type)
Index('ix_talkingpoint_competitor_dim', TalkingPoint.competitor_id, TalkingPoint.dimension_id)
Index('ix_talkingpoint_type_active', TalkingPoint.point_type, TalkingPoint.is_active)
Index('ix_dimnews_competitor_dim', DimensionNewsTag.competitor_id, DimensionNewsTag.dimension_id)
Index('ix_dimnews_tagged_at', DimensionNewsTag.tagged_at.desc())
Index('ix_news_competitor_published', NewsArticleCache.competitor_id, NewsArticleCache.published_at.desc())
Index('ix_news_source_sentiment', NewsArticleCache.source_type, NewsArticleCache.sentiment)
Index('ix_subscription_user_competitor', CompetitorSubscription.user_id, CompetitorSubscription.competitor_id)
Index('ix_team_membership_user', TeamMembership.team_id, TeamMembership.user_id)
Index('ix_annotation_competitor_team', CompetitorAnnotation.competitor_id, CompetitorAnnotation.team_id)
Index('ix_team_activity_team_type', TeamActivity.team_id, TeamActivity.activity_type)
Index('ix_chat_session_user_context', ChatSession.user_id, ChatSession.page_context)
Index('ix_chat_session_user_active', ChatSession.user_id, ChatSession.is_active, ChatSession.updated_at.desc())
Index('ix_chat_message_session_created', ChatMessage.session_id, ChatMessage.created_at)

# =============================================================================
# TABLE CREATION & DATABASE INITIALIZATION
# =============================================================================

# Create tables using sync engine
Base.metadata.create_all(bind=engine)

# PERF-005: Enable WAL mode for better concurrent access and performance (SQLite only)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Enable SQLite performance optimizations."""
        cursor = dbapi_connection.cursor()
        # WAL mode for better concurrent read/write performance
        cursor.execute("PRAGMA journal_mode=WAL")
        # Synchronous mode for better performance (still safe with WAL)
        cursor.execute("PRAGMA synchronous=NORMAL")
        # Larger cache for better read performance (64MB)
        cursor.execute("PRAGMA cache_size=-65536")
        # Enable foreign key enforcement
        cursor.execute("PRAGMA foreign_keys=ON")
        # Memory-mapped I/O for better read performance (256MB)
        cursor.execute("PRAGMA mmap_size=268435456")
        # Optimize temp storage
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()


# =============================================================================
# ASYNC UTILITY FUNCTIONS (v7.0)
# =============================================================================

async def init_async_db():
    """
    Initialize async database tables.

    Call this once on application startup when using async PostgreSQL.
    For SQLite, tables are created synchronously above.
    """
    if async_engine is None:
        logger.warning("Async engine not initialized, skipping async table creation")
        return

    # PostgreSQL tables are managed by Alembic migrations
    # This function is a placeholder for any async-specific initialization
    logger.info("Async database initialization complete")


# =============================================================================
# ASYNC CRUD HELPERS - SQLAlchemy 2.0 Patterns
# =============================================================================
# These helpers implement the SQLAlchemy 2.0 async query patterns.
# Use these in async endpoints instead of db.query().

async def get_competitor_by_id(session: AsyncSession, competitor_id: int):
    """Get competitor by ID."""
    result = await session.execute(
        select(Competitor).where(Competitor.id == competitor_id)
    )
    return result.scalar_one_or_none()


async def get_all_competitors(session: AsyncSession, limit: int = 100, include_deleted: bool = False):
    """Get all competitors with optional filtering."""
    query = select(Competitor)
    if not include_deleted:
        query = query.where(Competitor.is_deleted == False)
    query = query.order_by(Competitor.name).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


async def get_active_competitors(session: AsyncSession):
    """Get all active (non-deleted) competitors."""
    result = await session.execute(
        select(Competitor).where(Competitor.is_deleted == False).order_by(Competitor.name)
    )
    return result.scalars().all()


async def get_competitor_by_name(session: AsyncSession, name: str):
    """Get competitor by name (case-insensitive)."""
    from sqlalchemy import func
    result = await session.execute(
        select(Competitor).where(func.lower(Competitor.name) == func.lower(name))
    )
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str):
    """Get user by email."""
    result = await session.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int):
    """Get user by ID."""
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_news_articles(
    session: AsyncSession,
    days: int = 7,
    limit: int = 100,
    competitor_id: int = None
):
    """Get news articles with optional filtering."""
    from datetime import timedelta
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)
    query = select(NewsArticleCache).where(NewsArticleCache.published_at >= cutoff)

    if competitor_id:
        query = query.where(NewsArticleCache.competitor_id == competitor_id)

    query = query.order_by(NewsArticleCache.published_at.desc()).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


async def get_news_count(session: AsyncSession, days: int = 7):
    """Get count of news articles in the last N days."""
    from datetime import timedelta
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await session.execute(
        select(func.count(NewsArticleCache.id)).where(
            NewsArticleCache.published_at >= cutoff
        )
    )
    return result.scalar() or 0


async def get_system_prompt(session: AsyncSession, prompt_type: str, user_id: int = None):
    """Get system prompt by key, with optional user customization."""
    # First check for user-specific prompt
    if user_id:
        result = await session.execute(
            select(SystemPrompt).where(
                SystemPrompt.key == prompt_type,
                SystemPrompt.user_id == user_id
            )
        )
        prompt = result.scalar_one_or_none()
        if prompt:
            return prompt

    # Fall back to system default (user_id is NULL)
    result = await session.execute(
        select(SystemPrompt).where(
            SystemPrompt.key == prompt_type,
            SystemPrompt.user_id == None
        )
    )
    return result.scalar_one_or_none()


async def get_knowledge_base_items(session: AsyncSession, active_only: bool = True):
    """Get knowledge base items."""
    query = select(KnowledgeBaseItem)
    if active_only:
        query = query.where(KnowledgeBaseItem.is_active == True)
    result = await session.execute(query)
    return result.scalars().all()


async def get_change_history(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    competitor_id: int = None
):
    """Get change history with pagination."""
    query = select(DataChangeHistory)
    if competitor_id:
        query = query.where(DataChangeHistory.competitor_id == competitor_id)
    query = query.order_by(DataChangeHistory.changed_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return result.scalars().all()


async def count_competitors(session: AsyncSession, include_deleted: bool = False) -> int:
    """Count competitors."""
    from sqlalchemy import func
    query = select(func.count(Competitor.id))
    if not include_deleted:
        query = query.where(Competitor.is_deleted == False)
    result = await session.execute(query)
    return result.scalar() or 0


async def count_by_threat_level(session: AsyncSession) -> dict:
    """Count competitors by threat level."""
    from sqlalchemy import func
    result = await session.execute(
        select(Competitor.threat_level, func.count(Competitor.id))
        .where(Competitor.is_deleted == False)
        .group_by(Competitor.threat_level)
    )
    return dict(result.all())


async def create_competitor(session: AsyncSession, **kwargs) -> Competitor:
    """Create a new competitor."""
    competitor = Competitor(**kwargs)
    session.add(competitor)
    await session.commit()
    await session.refresh(competitor)
    return competitor


async def update_competitor(session: AsyncSession, competitor_id: int, **kwargs) -> Competitor:
    """Update a competitor."""
    from sqlalchemy import update
    await session.execute(
        update(Competitor).where(Competitor.id == competitor_id).values(**kwargs)
    )
    await session.commit()
    return await get_competitor_by_id(session, competitor_id)


async def delete_competitor(session: AsyncSession, competitor_id: int, soft_delete: bool = True):
    """Delete a competitor (soft delete by default)."""
    if soft_delete:
        await session.execute(
            select(Competitor).where(Competitor.id == competitor_id)
        )
        await update_competitor(session, competitor_id, is_deleted=True)
    else:
        from sqlalchemy import delete
        await session.execute(
            delete(Competitor).where(Competitor.id == competitor_id)
        )
        await session.commit()


async def get_products_by_competitor(session: AsyncSession, competitor_id: int):
    """Get products for a competitor."""
    result = await session.execute(
        select(CompetitorProduct).where(CompetitorProduct.competitor_id == competitor_id)
    )
    return result.scalars().all()


async def get_all_products(session: AsyncSession, limit: int = 1000):
    """Get all products."""
    result = await session.execute(
        select(CompetitorProduct).limit(limit)
    )
    return result.scalars().all()


async def get_data_sources(session: AsyncSession, competitor_id: int = None):
    """Get data sources with optional competitor filter."""
    query = select(DataSource)
    if competitor_id:
        query = query.where(DataSource.competitor_id == competitor_id)
    result = await session.execute(query)
    return result.scalars().all()


# Log database configuration on import
logger.info(f"Database URL (sync): {DATABASE_URL[:50]}...")
if ASYNC_DATABASE_URL:
    logger.info(f"Database URL (async): {ASYNC_DATABASE_URL[:50]}...")
