# Certify Intel v8.2.0 - API Reference

## Base URL

```
http://localhost:8000
```

## Authentication

All endpoints (except `/token`, `/health`, and `/api/version`) require a JWT bearer token:

```
Authorization: Bearer <token>
```

## Table of Contents

1. [Authentication](#authentication-1)
2. [Health & Status](#health--status)
3. [Competitors](#competitors)
4. [Dashboard](#dashboard)
5. [Analytics](#analytics)
6. [AI Tasks & Chat](#ai-tasks--chat)
7. [AI Generation](#ai-generation)
8. [AI Multimodal](#ai-multimodal)
9. [AI Agents](#ai-agents)
10. [Discovery Scout](#discovery-scout)
11. [News Feed](#news-feed)
12. [Sales & Marketing](#sales--marketing)
13. [Battlecards](#battlecards)
14. [Products & Pricing](#products--pricing)
15. [Customer Counts](#customer-counts)
16. [Data Quality & Sources](#data-quality--sources)
17. [Data Verification](#data-verification)
18. [Change Tracking](#change-tracking)
19. [Data Changes (Approval Workflow)](#data-changes-approval-workflow)
20. [Knowledge Base](#knowledge-base)
21. [Reconciliation](#reconciliation)
22. [Search](#search)
23. [Export](#export)
24. [Scrapers](#scrapers)
25. [User Management](#user-management)
26. [Prompts](#prompts)
27. [Settings & Scheduling](#settings--scheduling)
28. [Subscriptions & Alerts](#subscriptions--alerts)
29. [Win/Loss Deals](#winloss-deals)
30. [Webhooks](#webhooks)
31. [Backup & Recovery](#backup--recovery)
32. [Observability](#observability)

---

## Authentication

### Login

```
POST /token
Content-Type: application/x-www-form-urlencoded

username=[YOUR-ADMIN-EMAIL]&password=[YOUR-ADMIN-PASSWORD]
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

---

## Health & Status

### Basic Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "healthy"
}
```

### Application Version

```
GET /api/version
```

**Response:**
```json
{
  "version": "8.2.0",
  "name": "Certify Intel"
}
```

### Detailed Health

```
GET /api/health
```

### AI Provider Status

```
GET /api/ai/status
```

**Response:**
```json
{
  "status": "configured",
  "provider_config": "hybrid",
  "providers": {
    "anthropic": {"available": true, "model": "claude-opus-4-5"},
    "openai": {"available": true, "model": "gpt-4o-mini"},
    "gemini": {"available": true, "model": "gemini-3-flash-preview"}
  },
  "routing": {
    "data_extraction": "gemini",
    "executive_summary": "anthropic",
    "complex_analysis": "anthropic",
    "bulk_tasks": "gemini",
    "quality_tasks": "anthropic"
  },
  "budget": {
    "daily_budget_usd": 50.0,
    "today_spend_usd": 0.0234,
    "remaining_budget_usd": 49.9766,
    "budget_used_percent": 0.0,
    "budget_warning": false
  },
  "fallback_enabled": true
}
```

### Discovery Provider Status

```
GET /api/discovery/provider-status
```

Returns detailed diagnostics for all AI providers including Vertex AI status.

### Observability Status

```
GET /api/observability/status
```

**Response:**
```json
{
  "langfuse": {
    "enabled": false,
    "host": "http://localhost:3000",
    "connected": false,
    "error": "Langfuse disabled via ENABLE_LANGFUSE"
  },
  "setup_instructions": "1. docker-compose -f docker-compose.langfuse.yml up -d..."
}
```

---

## Competitors

### List All Competitors

```
GET /api/competitors
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Phreesia",
    "website": "https://phreesia.com",
    "threat_level": "High",
    "status": "Active",
    "product_categories": "Patient Intake;RCM",
    "employee_count": "1500",
    "data_quality_score": 85,
    ...
  }
]
```

### Get Single Competitor

```
GET /api/competitors/{competitor_id}
```

### Create Competitor

```
POST /api/competitors
Content-Type: application/json

{
  "name": "New Competitor",
  "website": "https://example.com",
  "threat_level": "Medium"
}
```

### Update Competitor

```
PUT /api/competitors/{competitor_id}
Content-Type: application/json

{
  "threat_level": "High",
  "employee_count": "500"
}
```

### Delete Competitor (Soft Delete)

```
DELETE /api/competitors/{competitor_id}
```

### Correct Competitor Data

```
POST /api/competitors/{competitor_id}/correct
Content-Type: application/json

{
  "field_name": "customer_count",
  "new_value": "3500",
  "source_url": "https://source.com/article",
  "notes": "Updated from Q4 2025 earnings"
}
```

### Bulk Operations

```
POST /api/competitors/bulk-update
PUT /api/competitors/bulk-update
DELETE /api/competitors/bulk-delete
POST /api/competitors/bulk-refresh
```

### Corporate Profile (Dashboard Stats)

```
GET /api/corporate-profile
```

**Response:**
```json
{
  "total_competitors": 74,
  "total_products": 789,
  "total_sources": 512,
  "total_news": 920,
  "high_threats": 15,
  "medium_threats": 35,
  "low_threats": 24
}
```

---

## Dashboard

### Dashboard Stats

```
GET /api/dashboard/stats
```

### Top Threats

```
GET /api/dashboard/top-threats
```

**Response:**
```json
[
  {
    "id": 5,
    "name": "Epic Systems",
    "threat_level": "High",
    "product_overlap_score": 85,
    "recent_changes": 3
  }
]
```

### Threat Level Trends

```
GET /api/dashboard/threat-trends
```

**Response:**
```json
{
  "labels": ["2026-W01", "2026-W02", "2026-W03"],
  "high": [2, 3, 1],
  "medium": [5, 4, 6],
  "low": [1, 2, 0]
}
```

---

## Analytics

### Analytics Summary

```
GET /api/analytics/summary
GET /api/analytics/executive-summary
```

### Market Quadrant

```
GET /api/analytics/market-quadrant
```

**Response:**
```json
{
  "competitors": [
    {
      "id": 1,
      "name": "Phreesia",
      "market_strength": 78.5,
      "growth_momentum": 65.2,
      "company_size": 25,
      "threat_level": "High"
    }
  ]
}
```

### Market Map

```
GET /api/analytics/market-map
```

### Threats Analysis

```
GET /api/analytics/threats
```

### Market Share

```
GET /api/analytics/market-share
```

### Pricing Analysis

```
GET /api/analytics/pricing
```

### Trend Endpoints

```
GET /api/analytics/trends
GET /api/analytics/sentiment-trend
GET /api/analytics/activity-trend
GET /api/analytics/growth-trend
GET /api/changes/trend
```

### Analytics Chat

```
POST /api/analytics/chat
Content-Type: application/json

{
  "message": "What are the top pricing trends?",
  "competitor_id": 5
}
```

---

## AI Tasks & Chat

### Create Background AI Task

```
POST /api/ai/tasks
Content-Type: application/json

{
  "task_type": "analysis",
  "prompt": "Analyze market position of Phreesia",
  "competitor_id": 5
}
```

**Response:**
```json
{
  "task_id": "abc-123",
  "status": "pending"
}
```

### Get Task Status

```
GET /api/ai/tasks/{task_id}
```

### List Pending Tasks

```
GET /api/ai/tasks/pending
```

### Dismiss Task

```
PUT /api/ai/tasks/{task_id}/read
```

### Chat Sessions

```
GET /api/chat/sessions                        # List user's sessions
POST /api/chat/sessions                       # Create new session
GET /api/chat/sessions/{session_id}           # Get session with messages
PUT /api/chat/sessions/{session_id}           # Update session title
DELETE /api/chat/sessions/{session_id}        # Delete session
GET /api/chat/sessions/{session_id}/messages  # Get messages
POST /api/chat/sessions/{session_id}/messages # Send message
GET /api/chat/sessions/by-context/{page}      # Get session by page context
```

### Create Chat Session

```
POST /api/chat/sessions
Content-Type: application/json

{
  "page_context": "dashboard",
  "competitor_id": 5,
  "title": "Q1 Threat Analysis"
}
```

### Send Chat Message

```
POST /api/chat/sessions/{session_id}/messages
Content-Type: application/json

{
  "content": "What are Epic's key weaknesses?",
  "prompt_key": "chat_persona"
}
```

---

## AI Generation

### AI Analysis

```
POST /api/ai/analyze
Content-Type: application/json

{
  "query": "Compare pricing strategies of top 5 competitors",
  "competitor_id": 5
}
```

### Generate Battlecard

```
POST /api/ai/generate-battlecard
Content-Type: application/json

{
  "competitor_id": 5,
  "focus_dimensions": ["pricing_flexibility", "product_packaging"],
  "deal_context": "Large hospital system, 500 beds",
  "prompt_key": "battlecard_generator"
}
```

### Battlecard Strategy

```
GET /api/ai/battlecard-strategy/{competitor_id}
```

### Grounded Search

```
POST /api/ai/search-grounded
Content-Type: application/json

{
  "query": "Phreesia latest funding round 2025",
  "competitor_id": 5
}
```

### Research Competitor

```
POST /api/ai/research-competitor
Content-Type: application/json

{
  "competitor_id": 5,
  "research_type": "deep"
}
```

### Deep Research

```
POST /api/ai/deep-research
Content-Type: application/json

{
  "query": "Healthcare patient intake market trends 2026",
  "max_sources": 10
}
```

### Process News Batch

```
POST /api/ai/process-news-batch
Content-Type: application/json

{
  "articles": [...],
  "analysis_type": "sentiment"
}
```

### Research Types & Providers

```
GET /api/ai/research-types
GET /api/ai/research-providers
```

---

## AI Multimodal

### Analyze Screenshot

```
POST /api/ai/analyze-screenshot
Content-Type: multipart/form-data

competitor_name: Phreesia
page_type: pricing
file: <screenshot.png>
```

### Analyze PDF

```
POST /api/ai/analyze-pdf
Content-Type: multipart/form-data

competitor_name: Phreesia
file: <document.pdf>
```

### Analyze Image

```
POST /api/ai/analyze-image
Content-Type: multipart/form-data

file: <image.png>
prompt: "Extract competitor information from this image"
```

### Analyze Video

```
POST /api/ai/analyze-video
Content-Type: multipart/form-data

file: <video.mp4>
prompt: "Summarize the product demo"
```

---

## AI Agents

### Agent Endpoints (LangGraph)

```
POST /api/agents/dashboard     # Dashboard agent query
POST /api/agents/battlecard    # Battlecard generation
POST /api/ai/news-agent        # News analysis agent
GET  /api/ai/news-agent/status # News agent status
GET  /api/agents/status        # All agents status
GET  /api/agents/cost          # Agent cost tracking
```

### Query an Agent

```
POST /api/agents/dashboard
Content-Type: application/json

{
  "query": "What are the top competitive threats this week?",
  "user_id": "user123"
}
```

**Response:**
```json
{
  "response": "Based on recent changes...",
  "agent": "dashboard",
  "model": "claude-opus-4-5",
  "citations": [...],
  "cost_usd": 0.0123,
  "latency_ms": 2450
}
```

---

## Discovery Scout

### Run AI Discovery

```
POST /api/discovery/run-ai
Content-Type: application/json

{
  "criteria": {
    "target_segments": ["hospital", "ambulatory"],
    "required_capabilities": ["pxp", "rcm"],
    "company_size": {"min_employees": 50},
    "geography": ["us"]
  },
  "prompt": "Find healthcare IT companies competing with patient intake platforms"
}
```

**Response:**
```json
{
  "task_id": "disc-456",
  "status": "started"
}
```

### Poll Discovery Progress

```
GET /api/discovery/progress/{task_id}
```

**Response:**
```json
{
  "status": "running",
  "stage": "qualifying",
  "stage_number": 2,
  "total_stages": 4,
  "candidates_found": 12,
  "message": "Qualifying 12 candidates..."
}
```

### Get Discovery Results

```
GET /api/discovery/results
```

### Clear Discovery Results

```
DELETE /api/discovery/results
```

### Summarize Discovery

```
POST /api/discovery/summarize
Content-Type: application/json

{
  "candidates": [...]
}
```

### Send to Battlecard / Comparison

```
POST /api/discovery/send-to-battlecard
POST /api/discovery/send-to-comparison
Content-Type: application/json

{
  "competitor_ids": [1, 5, 12]
}
```

### Discovery Profiles

```
GET    /api/discovery/profiles              # List profiles
GET    /api/discovery/profiles/{profile_id} # Get profile
POST   /api/discovery/profiles              # Create profile
DELETE /api/discovery/profiles/{profile_id} # Delete profile
```

### Default Prompt

```
GET /api/discovery/default-prompt
PUT /api/discovery/default-prompt
```

### Discovery History

```
GET /api/discovery/history
```

---

## News Feed

### Get News Feed

```
GET /api/news-feed?days=30&sentiment=negative&competitor_id=5
```

**Response:**
```json
[
  {
    "id": 1,
    "competitor_id": 5,
    "competitor_name": "Epic Systems",
    "title": "Epic Systems Launches New Patient Portal",
    "url": "https://...",
    "source": "Healthcare IT News",
    "source_type": "google_news",
    "published_at": "2026-02-10T14:30:00",
    "snippet": "Epic announced...",
    "sentiment": "positive",
    "event_type": "product_launch",
    "is_major_event": true
  }
]
```

### Competitor News

```
GET /api/competitors/{competitor_id}/news
```

### Fetch News (Trigger Refresh)

```
POST /api/news-feed/fetch
Content-Type: application/json

{
  "competitor_ids": [1, 5, 12]
}
```

### Fetch Progress

```
GET /api/news-feed/fetch-progress/{progress_key}
```

### Summarize News

```
POST /api/news-feed/summarize
Content-Type: application/json

{
  "article_ids": [1, 2, 3],
  "prompt_key": "news_summary"
}
```

### Summarize All News

```
POST /api/news-feed/summarize-all
Content-Type: application/json

{
  "days": 7,
  "prompt_key": "news_weekly_digest"
}
```

### Archive Article

```
PUT /api/news-feed/{article_id}/archive
```

### Cleanup Irrelevant Articles

```
POST /api/news-feed/cleanup-irrelevant
```

### Refresh News Cache

```
POST /api/news-feed/refresh-cache
```

### News Coverage

```
GET /api/news-coverage
POST /api/news-coverage/refresh-all
```

---

## Sales & Marketing

### Sales Playbook Generator

```
POST /api/sales-marketing/playbook/generate
Content-Type: application/json

{
  "competitor_id": 5,
  "deal_context": "500-bed hospital system, $2M deal",
  "prompt_key": "playbook_generator"
}
```

**Response:**
```json
{
  "competitor_id": 5,
  "competitor_name": "Epic Systems",
  "title": "Sales Playbook: Epic Systems",
  "content": "## Positioning\n...\n## Key Differentiators\n...",
  "playbook": "## Positioning\n...",
  "sections": ["Positioning", "Key Differentiators", "Objection Handling",
               "Pricing Strategy", "Proof Points", "Recommended Approach"],
  "provider": "anthropic",
  "model": "claude-opus-4-5"
}
```

### Dimension Endpoints (via router)

```
GET  /api/sales-marketing/dimensions
GET  /api/sales-marketing/competitors/{id}/dimensions
POST /api/sales-marketing/competitors/{id}/dimensions
POST /api/sales-marketing/compare/dimensions
POST /api/sales-marketing/battlecards/generate
GET  /api/sales-marketing/talking-points/{competitor_id}
```

---

## Battlecards

### Generate Battlecard Summaries

```
POST /api/battlecards/generate-summaries
Content-Type: application/json

{
  "competitor_ids": [1, 5, 12]
}
```

### SWOT Analysis

```
GET /api/competitors/{competitor_id}/swot
```

### Threat Analysis

```
GET /api/competitors/{competitor_id}/threat-analysis
```

---

## Products & Pricing

### Competitor Products

```
GET    /api/competitors/{competitor_id}/products
POST   /api/products
PUT    /api/products/{product_id}
DELETE /api/products/{product_id}
```

### Pricing Tiers

```
GET    /api/products/{product_id}/pricing-tiers
POST   /api/pricing-tiers
PUT    /api/pricing-tiers/{tier_id}
DELETE /api/pricing-tiers/{tier_id}
POST   /api/pricing-tiers/{tier_id}/verify
```

### Feature Matrix

```
GET    /api/products/{product_id}/features
POST   /api/features
DELETE /api/features/{feature_id}
GET    /api/features/compare
```

### Pricing Comparison

```
GET /api/pricing/compare
GET /api/pricing/models
GET /api/pricing/comparison
```

### AI Product Extraction

```
POST /api/competitors/{competitor_id}/extract-products
POST /api/products/{product_id}/extract-features
```

---

## Customer Counts

```
GET  /api/competitors/{competitor_id}/customer-counts
GET  /api/competitors/{competitor_id}/customer-count/latest
POST /api/customer-counts
PUT  /api/customer-counts/{count_id}
DELETE /api/customer-counts/{count_id}
POST /api/customer-counts/{count_id}/verify
GET  /api/customer-counts/compare
GET  /api/customer-counts/units
GET  /api/customer-counts/history/{competitor_id}
POST /api/competitors/{competitor_id}/triangulate-customer-count
```

---

## Data Quality & Sources

### Data Quality Overview

```
GET /api/data-quality/overview
```

**Response:**
```json
{
  "overall_score": 72,
  "total_sources": 512,
  "verified_sources": 440,
  "verification_rate": 85.9,
  "by_confidence": {
    "high": 280,
    "moderate": 150,
    "low": 82
  }
}
```

### Data Quality Endpoints

```
GET  /api/data-quality/completeness
GET  /api/data-quality/scores
GET  /api/data-quality/stale
GET  /api/data-quality/completeness/{competitor_id}
GET  /api/data-quality/low-confidence
GET  /api/data-quality/confidence-distribution
POST /api/data-quality/verify/{competitor_id}
POST /api/data-quality/recalculate-confidence
```

### Source Management

```
GET  /api/sources/batch
GET  /api/sources/{competitor_id}
GET  /api/sources/{competitor_id}/{field_name}
GET  /api/sources/field/{competitor_id}/{field_name}
POST /api/sources/set
POST /api/sources/set-with-confidence
POST /api/sources/verify/{competitor_id}/{field_name}
GET  /api/sources/coverage
GET  /api/source-types
```

### Source Discovery

```
POST /api/sources/discover/{competitor_id}
POST /api/sources/discover/all
GET  /api/sources/discover/status
```

### Data Triangulation

```
POST /api/triangulate/{competitor_id}
POST /api/triangulate/{competitor_id}/{field_name}
POST /api/triangulate/all
GET  /api/triangulation/status
```

---

## Data Verification

### AI-Powered Verification

```
POST /api/verification/run-all        # Batch verify all competitors
GET  /api/verification/progress        # Poll progress + ETA
POST /api/verification/run/{id}        # Verify single competitor
```

### Verification Summary

```
GET /api/competitors/{competitor_id}/verification-summary
```

**Response:**
```json
{
  "verified_fields": 45,
  "total_fields": 60,
  "verification_rate": 75.0,
  "last_verified_at": "2026-02-10T14:30:00"
}
```

### Source Links

```
GET /api/competitors/{competitor_id}/source-links
```

---

## Change Tracking

### List Changes

```
GET /api/changes?competitor_id=5&change_type=threat_level&days=30&limit=50&offset=0
```

**Response:**
```json
{
  "changes": [
    {
      "id": 123,
      "competitor_id": 5,
      "competitor_name": "Epic Systems",
      "change_type": "threat_level",
      "previous_value": "Medium",
      "new_value": "High",
      "source": "ai_analysis",
      "severity": "High",
      "detected_at": "2026-02-10T14:30:00"
    }
  ],
  "total": 45
}
```

### Change Detail

```
GET /api/changes/{change_id}/diff
```

### Rollback Change

```
POST /api/changes/{change_id}/rollback
```

### History & Timeline

```
GET /api/changes/history/{competitor_id}
GET /api/changes/timeline
GET /api/changes/field-history/{competitor_id}/{field_name}
```

### Export Changes

```
GET  /api/changes/export
POST /api/changes/bulk-export
```

### Activity Logs

```
GET /api/activity-logs
GET /api/activity-logs/summary
```

---

## Data Changes (Approval Workflow)

### Submit Data Change

```
POST /api/data-changes/submit
Content-Type: application/json

{
  "competitor_id": 5,
  "field_name": "customer_count",
  "new_value": "3500",
  "source_url": "https://source.com",
  "notes": "From Q4 earnings report"
}
```

### Review Pending Changes

```
GET /api/data-changes/pending
```

### Approve / Reject

```
POST /api/data-changes/{change_id}/approve
POST /api/data-changes/{change_id}/reject
```

### Approved Fields

```
GET /api/data-changes/approved-fields
```

---

## Knowledge Base

### Knowledge Base Items

```
GET    /api/admin/knowledge-base
POST   /api/admin/knowledge-base
DELETE /api/admin/knowledge-base/{item_id}
```

### Document Upload

```
POST /api/admin/knowledge-base/upload
Content-Type: multipart/form-data

file: <document.pdf>
title: "Q4 2025 Market Analysis"
category: "strategy"
```

### Upload with Extraction

```
POST /api/kb/upload-with-extraction
Content-Type: multipart/form-data

file: <document.pdf>
```

### Knowledge Base Import

```
GET  /api/knowledge-base/scan
GET  /api/knowledge-base/verification-queue
GET  /api/knowledge-base/competitor-names
GET  /api/knowledge-base/preview
POST /api/knowledge-base/import
POST /api/knowledge-base/verification/bulk-approve
```

### Document Extractions

```
GET /api/kb/documents/{document_id}/extractions
GET /api/competitors/{competitor_id}/kb-documents
```

---

## Reconciliation

### Conflict Management

```
GET /api/reconciliation/conflicts
PUT /api/reconciliation/resolve/{extraction_id}
```

### Reconciled Data

```
GET /api/competitors/{competitor_id}/reconciled/{field_name}
```

---

## Search

### Global Search

```
GET /api/search?q=patient+intake&limit=20
```

**Response:**
```json
{
  "competitors": [...],
  "products": [...],
  "news": [...],
  "total": 15
}
```

### Search Suggestions

```
GET /api/search/suggestions?q=phr
```

---

## Export

### PowerPoint Export

```
GET /api/export/pptx?competitor_ids=1,5,12
```

### JSON Export

```
GET /api/export/json
```

### Excel Export

```
GET /api/export/excel
```

### Competitor Data Export

```
POST /api/competitors/export
Content-Type: application/json

{
  "competitor_ids": [1, 5, 12],
  "format": "csv",
  "fields": ["name", "threat_level", "customer_count"]
}
```

---

## Scrapers

### Enhanced Scrape

```
POST /api/scrape/enhanced/{competitor_id}
GET  /api/scrape/enhanced/{competitor_id}/sources
```

### Batch Scrape

```
POST /api/scrape/all
GET  /api/scrape/progress
GET  /api/scrape/session
```

### Single Competitor Scrape

```
POST /api/scrape/{competitor_id}
```

### Generate AI Summary

```
POST /api/scrape/generate-summary
```

### Refresh History

```
GET /api/refresh-history
GET /api/refresh/history
```

### Firecrawl Integration

```
POST /api/firecrawl/scrape
POST /api/firecrawl/scrape-batch
POST /api/firecrawl/scrape-competitor
POST /api/firecrawl/crawl
GET  /api/firecrawl/crawl/{job_id}
GET  /api/firecrawl/status
```

---

## User Management

### List Users

```
GET /api/users
```

### Invite User

```
POST /api/users/invite
Content-Type: application/json

{
  "email": "analyst@company.com",
  "full_name": "Jane Analyst",
  "role": "analyst"
}
```

### Delete User

```
DELETE /api/users/{user_id}
```

---

## Prompts

### System Prompts (Admin)

```
GET  /api/admin/system-prompts                # List all (optional ?category=)
GET  /api/admin/system-prompts/categories     # List categories
GET  /api/admin/system-prompts/{key}          # Get by key
POST /api/admin/system-prompts               # Create/update prompt
```

### User Saved Prompts

```
GET    /api/user/prompts
POST   /api/user/prompts
GET    /api/user/prompts/{prompt_id}
PUT    /api/user/prompts/{prompt_id}
DELETE /api/user/prompts/{prompt_id}
POST   /api/user/prompts/{prompt_id}/set-default
```

### System Prompt Categories

| Category | Count | Purpose |
|----------|-------|---------|
| `battlecards` | 5 | Battlecard generation prompts |
| `competitor` | 2 | Competitor analysis prompts |
| `dashboard` | 7 | Dashboard summary prompts |
| `discovery` | 5 | Discovery scout prompts |
| `knowledge_base` | 17 | KB extraction and analysis |
| `news` | 5 | News summarization prompts |

---

## Settings & Scheduling

### Settings

```
POST /api/settings/schedule
GET  /api/settings/schedule
POST /api/settings/notifications
GET  /api/settings/notifications
GET  /api/settings/threat-criteria
POST /api/settings/threat-criteria
PUT  /api/user-settings/ai-insights
```

### Notification Rules

```
GET    /api/notifications/rules
POST   /api/notifications/rules
PUT    /api/notifications/rules/{rule_id}
DELETE /api/notifications/rules/{rule_id}
GET    /api/notifications
```

### Scheduler Control

```
GET  /api/scheduler/status
POST /api/scheduler/start
POST /api/scheduler/stop
POST /api/refresh/schedule
POST /api/refresh/trigger
```

---

## Subscriptions & Alerts

### Competitor Subscriptions

```
GET    /api/subscriptions
POST   /api/subscriptions
PUT    /api/subscriptions/{subscription_id}
DELETE /api/subscriptions/{subscription_id}
GET    /api/competitors/{competitor_id}/subscription
```

### Create Subscription

```
POST /api/subscriptions
Content-Type: application/json

{
  "competitor_id": 5,
  "notify_email": true,
  "notify_slack": false,
  "alert_on_pricing": true,
  "alert_on_products": true,
  "alert_on_news": true,
  "alert_on_threat_change": true,
  "min_severity": "Medium"
}
```

### Alerts

```
POST /api/alerts/send-digest
POST /api/alerts/send-summary
GET  /api/alerts/price-changes
GET  /api/alerts/email-log
DELETE /api/alerts/email-log
POST /api/alerts/test-email
```

---

## Win/Loss Deals

### List Deals

```
GET /api/win-loss
```

### Create Deal

```
POST /api/win-loss
Content-Type: application/json

{
  "competitor_id": 5,
  "outcome": "win",
  "deal_value": 250000,
  "customer_name": "Metro Health System",
  "customer_size": "Enterprise",
  "reason": "Better integration capabilities",
  "sales_rep": "John Smith",
  "notes": "Customer valued our FHIR support"
}
```

### Deal Stats & Analysis

```
GET /api/deals/stats
GET /api/deals/competitor/{competitor_id}
GET /api/deals/most-competitive
```

---

## Webhooks

```
GET    /api/webhooks
POST   /api/webhooks
DELETE /api/webhooks/{id}
POST   /api/webhooks/{webhook_id}/test
GET    /api/webhooks/events
```

### Create Webhook

```
POST /api/webhooks
Content-Type: application/json

{
  "name": "Slack Alerts",
  "url": "https://hooks.slack.com/services/...",
  "event_types": "threat_change,price_change,major_news"
}
```

---

## Backup & Recovery

```
POST /api/backup/create
GET  /api/backup/list
GET  /api/backup/download/{filename}
POST /api/backup/restore/{filename}
```

---

## Observability

### Langfuse Status

```
GET /api/observability/status
```

### Performance Metrics

```
POST /api/metrics/vitals
GET  /api/metrics/vitals/summary
```

### Cache Stats

```
GET  /api/cache/stats
POST /api/cache/invalidate
```

### WebSocket Stats

```
GET /api/ws/stats
```

---

## Additional Endpoints

### Reports

```
GET /api/reports/weekly-briefing
GET /api/reports/comparison
GET /api/reports/battlecard/{competitor_id}
```

### External Data

```
GET /api/news/{company_name}
GET /api/stock/{company_name}
GET /api/competitors/{competitor_id}/reviews
GET /api/reviews/compare
GET /api/reviews/certify-health
GET /api/reviews/competitor/{competitor_key}
GET /api/reviews/platforms
GET /api/competitors/{competitor_id}/linkedin
GET /api/competitors/{competitor_id}/hiring
GET /api/hiring/compare
GET /api/competitors/{competitor_id}/insights
GET /api/competitors/{competitor_id}/employee-reviews
GET /api/competitors/{competitor_id}/jobs
GET /api/competitors/{competitor_id}/sec-filings
GET /api/competitors/{competitor_id}/patents
GET /api/competitors/{competitor_id}/klas-ratings
GET /api/competitors/{competitor_id}/mobile-apps
GET /api/competitors/{competitor_id}/social-sentiment
GET /api/competitors/{competitor_id}/market-presence
GET /api/competitors/{competitor_id}/data-sources
```

### Comparisons

```
GET /api/innovations/compare
GET /api/social/compare
```

### Logo Proxy

```
GET /api/logo-proxy?domain=phreesia.com
```

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status Code | Meaning |
|------------|---------|
| 400 | Bad request (invalid input) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient role) |
| 404 | Resource not found |
| 422 | Validation error (Pydantic) |
| 500 | Internal server error |

Error details never expose internal implementation. Server-side details are logged via `logger.error()`.

---

## Rate Limiting

- AI endpoints are governed by the daily budget (`AI_DAILY_BUDGET_USD`)
- Gemini calls have a 1-second delay between batch operations
- News fetch uses `asyncio.gather()` with ThreadPoolExecutor (10 workers)
- No explicit per-endpoint rate limiting (relies on provider-level limits)

---

*API Reference for Certify Intel v8.2.0 - February 2026*
