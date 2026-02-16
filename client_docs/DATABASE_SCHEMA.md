# Database Schema Reference

Certify Intel uses SQLAlchemy ORM with SQLite (default) or PostgreSQL (production).

All models are defined in `backend/database.py`.

---

## Core Tables

### `competitors` (Primary Entity)
The central table with 115+ columns tracking competitor companies.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-increment ID |
| `name` | String | Company name |
| `website` | String | Company website URL |
| `description` | Text | Company description |
| `threat_level` | String | "High", "Medium", or "Low" (string, not integer) |
| `is_deleted` | Boolean | Soft delete flag (default False) |
| `headquarters` | String | HQ location |
| `founded_year` | Integer | Year founded |
| `employee_count` | String | Employee range |
| `annual_revenue` | String | Revenue estimate |
| `funding_total` | String | Total funding raised |
| `market_segment` | String | Primary market segment |
| `key_products` | Text | Comma-separated product names |
| `target_customers` | Text | Target customer description |
| `pricing_model` | String | Pricing approach |
| `geographic_reach` | String | Geographic coverage |
| `last_scraped` | DateTime | Last data refresh timestamp |
| `data_confidence` | Float | Overall data confidence score (0-1) |
| `dim_*` | Float | 9 dimension scores (product, market_presence, pricing, etc.) |
| `social_*` | Various | Social media metrics |
| `financial_*` | Various | Financial data fields |
| `source_*` | Various | Source tracking fields |
| `url_*` | Various | Deep link/URL quality fields |

**Important**: `threat_level` is a String. Never compare with integers.

### `change_logs`
Tracks all data changes for audit trail.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | |
| `competitor_id` | Integer (FK) | Reference to competitor |
| `field_name` | String | Which field changed |
| `old_value` | Text | Previous value |
| `new_value` | Text | New value |
| `changed_by` | String | Who made the change |
| `changed_at` | DateTime | When it changed |
| `source` | String | Data source of change |

### `data_sources`
Tracks data provenance with source URLs and confidence scoring.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | |
| `competitor_id` | Integer (FK) | |
| `field_name` | String | Which competitor field this sources |
| `source_url` | String | URL of the source |
| `source_type` | String | Type (website, report, news, etc.) |
| `confidence_score` | Float | How confident we are in this data (0-1) |
| `last_verified` | DateTime | Last verification date |
| `url_status` | String | "verified", "pending", or "broken" |
| `page_url` | String | Specific page URL (deep link) |
| `content_match` | Text | Matched text on the page |
| `match_strategy` | String | How the match was found |
| `text_fragment` | String | W3C Text Fragment URL |

---

## Product Tables

### `competitor_products`
Product-level detail for each competitor.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | |
| `competitor_id` | Integer (FK) | |
| `name` | String | Product name |
| `category` | String | Product category |
| `description` | Text | Product description |
| `target_market` | String | Who it's for |
| `pricing_model` | String | How it's priced |
| `key_features` | Text | JSON list of features |

### `product_pricing_tiers`
Tiered pricing for products.

### `product_feature_matrix`
Feature comparison data across products.

---

## User & Authentication Tables

### `users`
| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | |
| `email` | String (unique) | Login email |
| `password_hash` | String | PBKDF2-HMAC-SHA256 hash |
| `full_name` | String | Display name |
| `role` | String | "admin" or "user" |
| `is_active` | Boolean | Account active flag |
| `mfa_enabled` | Boolean | TOTP MFA enabled |
| `mfa_secret` | String | TOTP secret (encrypted) |
| `mfa_backup_codes` | Text | JSON array of hashed backup codes |
| `created_at` | DateTime | Account creation |

### `refresh_tokens`
JWT refresh token storage for secure token rotation.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | |
| `token` | String (unique) | The refresh token |
| `user_id` | Integer (FK) | |
| `expires_at` | DateTime | Expiration time |
| `revoked` | Boolean | Whether revoked |

### `user_settings`
Per-user preference storage (JSON key-value).

### `user_saved_prompts`
User's saved custom AI prompts.

---

## AI & Chat Tables

### `chat_sessions`
Persistent chat sessions per user.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | |
| `user_id` | Integer (FK) | |
| `page_context` | String | Which page the chat was on |
| `competitor_id` | Integer (FK, nullable) | Associated competitor |
| `title` | String | Auto-generated session title |
| `is_active` | Boolean | Active flag |

### `chat_messages`
Individual messages within chat sessions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | |
| `session_id` | Integer (FK) | |
| `role` | String | "user" or "assistant" |
| `content` | Text | Message content |
| `metadata_json` | Text | JSON metadata (model used, tokens, etc.) |

### `system_prompts`
41 seeded system prompts across 6 categories, user-overridable.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | |
| `key` | String (unique) | Prompt identifier (e.g., "battlecard_generation") |
| `category` | String | Category (discovery, battlecard, analysis, etc.) |
| `title` | String | Human-readable name |
| `content` | Text | The prompt template |
| `user_id` | Integer (FK, nullable) | Null = global, set = user override |

---

## Intelligence Tables

### `battlecards`
Generated sales battlecards.

### `talking_points`
Sales talking points per competitor.

### `win_loss_deals`
Competitive deal tracking (wins and losses).

### `webhook_configs`
Webhook integration configurations.

### `discovery_profiles`
Saved Discovery Scout search criteria.

### `knowledge_base_items`
Internal knowledge base documents for RAG.

### `activity_logs`
User activity audit trail.

---

## Adding New Tables

1. Define the model in `database.py`:
   ```python
   class MyNewTable(Base):
       __tablename__ = "my_new_table"
       id = Column(Integer, primary_key=True, autoincrement=True)
       name = Column(String, nullable=False)
       created_at = Column(DateTime, default=datetime.utcnow)
   ```

2. Add table creation in `init_db()` (SQLite):
   ```python
   Base.metadata.create_all(bind=engine)
   ```

3. For adding columns to existing tables (SQLite):
   ```python
   try:
       cursor.execute("ALTER TABLE my_table ADD COLUMN new_col TEXT DEFAULT ''")
   except Exception:
       pass  # Column already exists
   ```

4. For PostgreSQL, use Alembic migrations (see `docs/POSTGRESQL_MIGRATION_GUIDE.md`).

---

## Database Access Patterns

### In Endpoints (Recommended)
```python
from dependencies import get_db

@router.get("/items")
async def get_items(db=Depends(get_db)):
    items = db.query(MyModel).all()
    return items
```

### In Background Tasks
```python
from database import SessionLocal

db = SessionLocal()
try:
    # Do work
    db.commit()
finally:
    db.close()
```

### Async Pattern (PostgreSQL)
```python
from dependencies import get_async_db
from sqlalchemy import select

@router.get("/items")
async def get_items(db=Depends(get_async_db)):
    result = await db.execute(select(MyModel))
    return result.scalars().all()
```
