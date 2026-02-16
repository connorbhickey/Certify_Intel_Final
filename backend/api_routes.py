"""
Certify Intel - Extended API Routes
Additional endpoints for analytics, win/loss, auth, reports, and frontend serving
"""
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
# OAuth2 imports moved to routers/auth.py
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from typing import Optional, List
from datetime import datetime, timedelta
import os
from pydantic import BaseModel

# Import DB dependencies
from database import get_db, SystemSetting, SessionLocal
from sqlalchemy.orm import Session

# Import extended features
from extended_features import (
    win_loss_tracker, rate_limiter, cache_manager,
    similarweb_scraper, social_monitor,
    WinLossRecord, ClassificationWorkflow
)
from analytics import AnalyticsEngine
from reports import ReportManager
from external_scrapers import ExternalDataCollector
from data_enrichment import data_enrichment, ClearbitLogoService

router = APIRouter()

# Authentication endpoints moved to routers/auth.py


@router.get("/api/notifications")
async def get_notifications(limit: int = 10, db: Session = Depends(get_db)):
    """Get recent notifications (change logs)."""
    # Import ChangeLog locally to avoid circular issues if any
    from database import ChangeLog

    notifications = db.query(ChangeLog).order_by(ChangeLog.detected_at.desc()).limit(limit).all()

    return [
        {
            "id": n.id,
            "competitor_name": n.competitor_name,
            "change_type": n.change_type,
            "severity": n.severity,
            "detected_at": n.detected_at,
            "new_value": n.new_value[:100] + "..." if n.new_value and len(n.new_value) > 100 else n.new_value
        }
        for n in notifications
    ]


# ============== NOTIF-001: Notification Configuration ==============

@router.get("/api/notifications/config")
async def get_notification_config():
    """Get current notification configuration status."""
    import os

    return {
        "email": {
            "configured": bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD")),
            "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "from_email": os.getenv("ALERT_FROM_EMAIL", ""),
            "recipients": os.getenv("ALERT_TO_EMAILS", "").split(",") if os.getenv("ALERT_TO_EMAILS") else []
        },
        "slack": {
            "configured": bool(os.getenv("SLACK_WEBHOOK_URL")),
            "webhook_configured": "***" if os.getenv("SLACK_WEBHOOK_URL") else None
        },
        "teams": {
            "configured": bool(os.getenv("TEAMS_WEBHOOK_URL")),
            "webhook_configured": "***" if os.getenv("TEAMS_WEBHOOK_URL") else None
        },
        "sms": {
            "configured": bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")),
            "from_number": os.getenv("TWILIO_FROM_NUMBER", ""),
            "to_numbers": os.getenv("TWILIO_TO_NUMBERS", "").split(",") if os.getenv("TWILIO_TO_NUMBERS") else []
        }
    }


class TestEmailRequest(BaseModel):
    recipient: Optional[str] = None


@router.post("/api/notifications/test-email")
async def test_email_notification(request: TestEmailRequest = None):
    """Send a test email to verify SMTP configuration."""
    import os
    from alerts import AlertSystem

    # Check if email is configured
    if not os.getenv("SMTP_USER") or not os.getenv("SMTP_PASSWORD"):
        raise HTTPException(
            status_code=400,
            detail="Email not configured. Set SMTP_USER and SMTP_PASSWORD in .env"
        )

    alert_system = AlertSystem()

    # Override recipient if provided
    if request and request.recipient:
        alert_system.config.to_emails = [request.recipient]

    if not alert_system.config.to_emails:
        raise HTTPException(
            status_code=400,
            detail="No recipients configured. Set ALERT_TO_EMAILS in .env or provide recipient"
        )

    # Send test email
    subject = "Certify Intel - Test Email Configuration"
    html_body = """
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <div style="background: #2F5496; color: white; padding: 20px; border-radius: 8px;">
            <h1>Email Configuration Test</h1>
        </div>
        <div style="padding: 20px;">
            <p>Congratulations! Your email notification system is working correctly.</p>
            <p>You will now receive alerts for:</p>
            <ul>
                <li>Competitor pricing changes</li>
                <li>Funding announcements</li>
                <li>G2 rating changes</li>
                <li>Daily/weekly summaries</li>
            </ul>
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This is an automated test from Certify Intel.
            </p>
        </div>
    </body>
    </html>
    """

    success = alert_system.send_alert(subject, html_body, "Email configuration test successful!")

    if success:
        return {
            "success": True,
            "message": f"Test email sent to {', '.join(alert_system.config.to_emails)}"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test email. Check SMTP credentials and server logs."
        )


@router.get("/api/notifications/rules")
async def get_notification_rules():
    """Get all configured alert rules."""
    from notifications import NotificationManager

    manager = NotificationManager()
    return {
        "rules": manager.get_alert_rules(),
        "total": len(manager.rule_engine.rules)
    }


class AlertRuleRequest(BaseModel):
    id: str
    name: str
    competitor: Optional[str] = None
    field: str
    condition: str
    value: Optional[str] = None
    severity: str = "Medium"
    channels: List[str] = ["email"]
    active: bool = True


@router.post("/api/notifications/rules")
async def add_notification_rule(rule: AlertRuleRequest):
    """Add a new alert rule."""
    from notifications import NotificationManager, AlertRule

    manager = NotificationManager()
    new_rule = AlertRule(
        id=rule.id,
        name=rule.name,
        competitor=rule.competitor,
        field=rule.field,
        condition=rule.condition,
        value=rule.value,
        severity=rule.severity,
        channels=rule.channels,
        active=rule.active
    )
    manager.rule_engine.add_rule(new_rule)

    return {
        "success": True,
        "message": f"Rule '{rule.name}' added successfully",
        "rule": rule.dict()
    }


@router.delete("/api/notifications/rules/{rule_id}")
async def delete_notification_rule(rule_id: str):
    """Delete an alert rule."""
    from notifications import NotificationManager

    manager = NotificationManager()
    manager.rule_engine.remove_rule(rule_id)

    return {
        "success": True,
        "message": f"Rule '{rule_id}' deleted"
    }


# ============== Corporate Profile (Certify Health) ==============

@router.get("/api/corporate-profile")
async def get_corporate_profile():
    """
    Get Certify Health's corporate profile for the reference battlecard.
    This is the company users are comparing competitors against.
    """
    return {
        "id": "certify-health",
        "name": "Certify Health",
        "is_corporate": True,  # Flag to distinguish from competitors
        "website": "https://www.certifyhealth.com",
        "tagline": "Unified Healthcare Platform - From Check-In to Payment",
        
        # Company Info
        "year_founded": "2012",
        "headquarters": "Gaithersburg, Maryland, USA",
        "employee_count": "100-150",
        "employee_growth_rate": "+19% YoY",
        "offices": ["Gaithersburg, MD (HQ)", "Bengaluru, India"],
        
        # Funding & Financials
        "funding_total": "$10M Series A",
        "latest_round": "Series A",
        "investors": ["ABS Capital Partners"],
        "is_public": False,
        
        # Products (7 Core Platforms)
        "products": {
            "pxp": {
                "name": "Patient Experience Platform",
                "description": "Intake, scheduling, communication, engagement",
                "features": ["Self-Scheduling", "Digital Intake", "Reminders & Nudges", "Patient Portal", "Post-Visit Experience"]
            },
            "pms": {
                "name": "Practice Management System",
                "description": "Operations, staff tasking, reporting, compliance",
                "features": ["Scheduling & Appointments", "Registration", "Eligibility & Coverage", "Front/Back Office Ops", "Billing & RCM Ops"]
            },
            "rcm": {
                "name": "Revenue Cycle Management",
                "description": "Claims, payments, analytics, merchant services",
                "features": ["Patient Payments", "Claims Submission", "Denial Management", "Text-to-Pay", "AutoPay"]
            },
            "patient_mgmt": {
                "name": "Patient Management (EHR)",
                "description": "Charts, documentation, encounter tools, care coordination",
                "features": ["Patient Chart & Timeline", "Clinical Documentation", "AI-Powered Scribe", "Care Coordination", "Orders & Results"]
            },
            "certify_pay": {
                "name": "CERTIFY Pay",
                "description": "Omnichannel payment gateway for healthcare",
                "features": ["Payment Gateway", "Merchant Services", "Transaction Logs", "Chargebacks", "Payouts"]
            },
            "facecheck": {
                "name": "FaceCheck™",
                "description": "Biometric patient authentication",
                "features": ["Facial Recognition", "Touchless ID", "Fraud Prevention", "Expedited Check-In"]
            },
            "interoperability": {
                "name": "Interoperability",
                "description": "FHIR/HL7-driven integrations with all major EHRs",
                "features": ["Epic", "Cerner", "Athena", "NextGen", "eClinicalWorks", "Allscripts"]
            }
        },
        
        # Markets Served (11 Verticals)
        "markets": [
            "Hospitals & Health Systems",
            "Ambulatory & Outpatient Care",
            "Long-Term & Rehabilitation Care",
            "Behavioral Health & Human Services",
            "Specialized Care Facilities",
            "Telehealth & Digital Healthcare",
            "Laboratory & Diagnostic Services",
            "Managed Care & Health Insurance",
            "Multi-Specialty Groups & Enterprises",
            "Occupational & Corporate Healthcare",
            "Government & Public Health"
        ],
        
        # Key Differentiators
        "key_differentiators": [
            "Unified platform (not fragmented point solutions)",
            "EHR-agnostic with deep integrations",
            "FaceCheck™ biometric authentication",
            "AI-powered clinical documentation",
            "End-to-end patient journey coverage",
            "HIPAA-compliant, SOC 2 certified"
        ],
        
        # Metrics & ROI
        "claimed_outcomes": {
            "no_show_reduction": "30% fewer no-shows",
            "revenue_increase": "25% more revenue collected",
            "staff_hours_saved": "60+ staff hours saved monthly",
            "claim_denial_reduction": "20% reduction in claim denials",
            "digital_checkin_rate": "66% of patients check in digitally",
            "roi": "5-10x ROI on subscription"
        },
        
        # Certifications & Compliance
        "certifications": ["HIPAA Compliant", "SOC 2 Type II", "HITRUST CSF"],
        
        # Customer Segments
        "customer_size_focus": "Small to Enterprise (all sizes)",
        "geographic_focus": "United States (Primary), International Expansion",
        
        # Mission & Vision
        "mission": "Simpler Healthcare, Better Outcomes",
        "vision": "Connected Care, End to End - Patients move through a frictionless journey from scheduling to payment.",
        
        # Awards & Recognition
        "awards": ["Healthcare Innovation Red Hot Company 2025"],
        
        # Contact
        "contact": {
            "demo_url": "https://www.certifyhealth.com/market-study/",
            "support_url": "https://support.certifyglobal.com/portal/en/home"
        }
    }


# ============== Data Enrichment (Free APIs) ==============

@router.get("/api/logo/{domain}")
async def get_company_logo(domain: str):
    """Get company logo URL from Clearbit."""
    logo_url = ClearbitLogoService.get_logo_url(domain)
    return {"domain": domain, "logo_url": logo_url}


@router.get("/api/logo-proxy")
async def proxy_logo(url: str):
    """Proxy image requests to bypass CORS/SSL issues."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, follow_redirects=True, timeout=5.0)
            if resp.status_code == 200:
                from fastapi import Response
                return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/png"))
    except Exception:
        pass
    
    # Fallback SVG if failed
    from fastapi.responses import Response
    return Response(content='<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#e2e8f0"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" fill="#64748b" font-size="14">?</text></svg>', media_type="image/svg+xml")


@router.post("/api/enrich/batch-logos")
async def batch_enrich_logos(db: Session = Depends(get_db)):
    """Add logo URLs to all competitors missing logos."""
    from database import Competitor
    
    competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False,
        (Competitor.logo_url == None) | (Competitor.logo_url == "")
    ).all()
    
    updated = 0
    for comp in competitors:
        if comp.website:
            logo_url = ClearbitLogoService.get_logo_url(comp.website)
            comp.logo_url = logo_url
            updated += 1
    
    db.commit()
    
    return {"updated": updated, "total": len(competitors)}


@router.post("/api/enrich/{competitor_id}")
async def enrich_competitor(
    competitor_id: int,
    include_contacts: bool = False,
    db: Session = Depends(get_db)
):
    """
    Enrich competitor data from free APIs.
    - Clearbit: Logo
    - SEC EDGAR: Financials (if public)
    - Hunter.io: Contacts (optional, uses quota)
    """
    from database import Competitor
    
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    enriched = await data_enrichment.enrich_competitor(
        name=competitor.name,
        website=competitor.website,
        is_public=competitor.is_public or False,
        include_contacts=include_contacts
    )
    
    # Update competitor record
    for key, value in enriched.items():
        if hasattr(competitor, key):
            setattr(competitor, key, value)
    
    db.commit()
    
    return {
        "competitor_id": competitor_id,
        "enriched_fields": list(enriched.keys()),
        "data": enriched
    }


@router.get("/api/sec/{company_name}")
async def get_sec_data(company_name: str):
    """Get SEC EDGAR data for a public company."""
    sec_data = await data_enrichment.sec.enrich_competitor(company_name, is_public=True)
    return {"company": company_name, "sec_data": sec_data}


@router.get("/api/news-search/{company_name}")
async def search_company_news(company_name: str):
    """Search for company news using Google Custom Search."""
    if not data_enrichment.google.is_configured:
        return {"error": "Google Search API not configured", "hint": "Set GOOGLE_API_KEY and GOOGLE_CX in .env"}
    
    news = await data_enrichment.search_competitor_news(company_name)
    return {"company": company_name, "results": news}


# ============== Win/Loss Database ==============

@router.get("/api/winloss")
async def get_winloss_records(
    competitor: Optional[str] = None,
    outcome: Optional[str] = None
):
    """Get win/loss records."""
    records = win_loss_tracker.get_records(competitor, outcome)
    return {
        "records": [
            {
                "id": r.id,
                "competitor_name": r.competitor_name,
                "outcome": r.outcome,
                "deal_value": r.deal_value,
                "deal_date": r.deal_date.isoformat() if r.deal_date else None,
                "customer_name": r.customer_name,
                "customer_size": r.customer_size,
                "loss_reason": r.loss_reason,
                "win_factor": r.win_factor,
                "sales_rep": r.sales_rep,
                "notes": r.notes
            }
            for r in records
        ],
        "count": len(records)
    }


@router.post("/api/winloss")
async def add_winloss_record(
    competitor_name: str,
    outcome: str,
    deal_value: Optional[float] = None,
    customer_name: Optional[str] = None,
    customer_size: Optional[str] = None,
    loss_reason: Optional[str] = None,
    win_factor: Optional[str] = None,
    sales_rep: Optional[str] = None,
    notes: Optional[str] = None
):
    """Add a new win/loss record."""
    record = WinLossRecord(
        id=0,
        competitor_id=None,
        competitor_name=competitor_name,
        outcome=outcome,
        deal_value=deal_value,
        customer_name=customer_name,
        customer_size=customer_size,
        loss_reason=loss_reason,
        win_factor=win_factor,
        sales_rep=sales_rep,
        notes=notes
    )
    win_loss_tracker.add_record(record)
    return {"message": "Record added", "id": record.id}


@router.get("/api/winloss/stats")
async def get_winloss_stats():
    """Get win/loss statistics."""
    return win_loss_tracker.get_stats()


# ============== Analytics ==============

analytics_engine = AnalyticsEngine()

@router.get("/api/analytics/competitor/{competitor_id}")
async def get_competitor_analysis(competitor_id: int):
    """Get full analytics for a competitor."""
    from database import SessionLocal, Competitor
    
    db = SessionLocal()
    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    db.close()
    
    if not comp:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    # Convert to dict
    comp_dict = {
        "name": comp.name,
        "website": comp.website,
        "threat_level": comp.threat_level,
        "target_segments": comp.target_segments,
        "customer_size_focus": comp.customer_size_focus,
        "funding_total": comp.funding_total,
        "employee_growth_rate": comp.employee_growth_rate,
        "product_categories": comp.product_categories,
        "customer_count": comp.customer_count,
        "base_price": comp.base_price,
        "pricing_model": comp.pricing_model,
        "recent_launches": comp.recent_launches,
        "key_features": comp.key_features,
        "g2_rating": comp.g2_rating,
        "year_founded": comp.year_founded,
        "headquarters": comp.headquarters,
        "employee_count": comp.employee_count,
        "latest_round": comp.latest_round,
    }
    
    return analytics_engine.full_analysis(comp_dict)


@router.get("/api/analytics/heatmap")
async def get_competitive_heatmap():
    """Get competitive heatmap data."""
    from database import SessionLocal, Competitor
    
    db = SessionLocal()
    comps = db.query(Competitor).filter(Competitor.is_deleted == False).all()
    db.close()
    
    comp_dicts = [{"name": c.name, "threat_level": c.threat_level} for c in comps]
    
    return analytics_engine.heatmap_generator.generate_heatmap_data(comp_dicts)


# ============== External Data ==============

external_collector = ExternalDataCollector()

@router.get("/api/external/{competitor_name}")
async def get_external_data(competitor_name: str):
    """Get external data for a competitor (G2, LinkedIn, News, etc.)."""
    # Check cache first
    cache_key = f"external:{competitor_name.lower()}"
    cached = cache_manager.get(cache_key)
    if cached:
        return cached
    
    # Collect fresh data
    data = await external_collector.collect_all(competitor_name)
    
    # Cache for 1 hour
    cache_manager.set(cache_key, data, ttl=3600)
    
    return data


@router.get("/api/traffic/{domain}")
async def get_traffic_data(domain: str):
    """Get SimilarWeb traffic data for a domain."""
    data = await similarweb_scraper.get_traffic_data(domain)
    return {
        "domain": data.domain,
        "total_visits": data.total_visits,
        "avg_visit_duration": data.avg_visit_duration,
        "pages_per_visit": data.pages_per_visit,
        "bounce_rate": data.bounce_rate,
        "traffic_sources": data.traffic_sources,
        "top_countries": data.top_countries
    }


@router.get("/api/social/{competitor_name}")
async def get_social_mentions(competitor_name: str, days: int = 7):
    """Get social media mentions for a competitor."""
    posts = await social_monitor.search_mentions(competitor_name, days)
    sentiment = social_monitor.analyze_sentiment(posts)
    
    return {
        "posts": [
            {
                "platform": p.platform,
                "content": p.content,
                "url": p.url,
                "author": p.author,
                "engagement": p.engagement,
                "sentiment": p.sentiment
            }
            for p in posts
        ],
        "sentiment_analysis": sentiment
    }


# ============== Reports ==============

report_manager = ReportManager("./reports")

@router.get("/api/reports/weekly-briefing")
async def generate_weekly_briefing():
    """Generate and return weekly executive briefing PDF."""
    from database import SessionLocal, Competitor, ChangeLog
    
    db = SessionLocal()
    competitors = db.query(Competitor).filter(Competitor.is_deleted == False).all()
    
    # Get recent changes
    week_ago = datetime.utcnow() - timedelta(days=7)
    changes = db.query(ChangeLog).filter(ChangeLog.detected_at >= week_ago).all()
    
    db.close()
    
    comp_dicts = [{"name": c.name, "threat_level": c.threat_level, "customer_count": c.customer_count} for c in competitors]
    change_dicts = [
        {
            "competitor_name": c.competitor_name,
            "change_type": c.change_type,
            "previous_value": c.previous_value,
            "new_value": c.new_value,
            "severity": c.severity
        }
        for c in changes
    ]
    
    stats = {
        "total_competitors": len(competitors),
        "high_threat": len([c for c in competitors if c.threat_level and c.threat_level.upper() == "HIGH"]),
        "medium_threat": len([c for c in competitors if c.threat_level and c.threat_level.upper() == "MEDIUM"]),
        "low_threat": len([c for c in competitors if c.threat_level and c.threat_level.upper() == "LOW"])
    }
    
    path = report_manager.generate_weekly_briefing(comp_dicts, change_dicts, stats)
    
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"certify_intel_briefing_{datetime.now().strftime('%Y%m%d')}.pdf"
    )


@router.get("/api/reports/battlecard/{competitor_id}")
async def generate_battlecard(competitor_id: int):
    """Generate and return competitor battlecard PDF."""
    from database import SessionLocal, Competitor
    # Import Scrapers
    from linkedin_tracker import LinkedInTracker
    from google_ecosystem_scraper import GoogleEcosystemScraper
    from sentiment_scraper import SentimentScraper
    from tech_stack_scraper import TechStackScraper
    from seo_scraper import SEOScraper
    from risk_management_scraper import RiskManagementScraper
    
    db = SessionLocal()
    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    db.close()
    
    if not comp:
        raise HTTPException(status_code=404, detail="Competitor not found")

    # Fetch Real-time Intelligence
    linkedin = LinkedInTracker()
    google = GoogleEcosystemScraper()
    sentiment = SentimentScraper()
    tech = TechStackScraper()
    seo = SEOScraper()
    risk = RiskManagementScraper()

    li_data = linkedin.get_company_data(comp.name)
    google_data = google.get_ecosystem_data(comp.name)
    sent_data = sentiment.get_sentiment_data(comp.name)
    tech_data = tech.get_tech_stack(comp.name)
    seo_data = seo.get_seo_data(comp.name)
    risk_data = risk.get_risk_data(comp.name)

    # Calculate Data Points
    est_rev = (li_data.employee_count or 0) * 150000
    stage = "Late Stage VC" 
    if li_data.employee_count < 50: stage = "Seed/Early"
    elif li_data.employee_count < 200: stage = "Growth Stage"
    elif li_data.employee_count > 1000:
        if google_data.ads.active_creative_count > 100: stage = "Mass Market"
        else: stage = "Pre-IPO / PE"
    
    comp_dict = {
        "name": comp.name,
        "website": comp.website,
        "threat_level": comp.threat_level,
        "year_founded": comp.year_founded,
        "headquarters": comp.headquarters,
        "employee_count": comp.employee_count,
        "customer_count": comp.customer_count,
        "funding_total": comp.funding_total,
        "pricing_model": comp.pricing_model,
        "base_price": comp.base_price,
        "product_categories": comp.product_categories,
        "key_features": comp.key_features,
        "target_segments": comp.target_segments,
        "g2_rating": comp.g2_rating,
        "latest_round": comp.latest_round,
        # Deep Dive Data Structure
        "deep_dive": {
            "capital": {
                "est_revenue": f"${est_rev:,.0f}" if est_rev else "N/A",
                "funding_total": comp.funding_total,
                "stage": stage
            },
            "growth": {
                "headcount": li_data.employee_count,
                "growth_rate": li_data.employee_growth_6mo,
                "active_hiring": li_data.open_jobs
            },
            "digital": {
                "ads_active": google_data.ads.active_creative_count,
                "brand_index": google_data.trends.current_index,
                "trend": google_data.trends.trend_direction,
                "review_velocity": google_data.maps.reviews_last_month,
                "tech_signal": tech_data.marketing_budget_signal
            },
            "sentiment": {
                "g2_score": sent_data.g2_score
            },
            "seo": {
                "da": seo_data.domain_authority
            },
            "risk": {
                "founder_exit": "Exited Founder" if risk_data.founder_exits else "Standard",
                "warn": risk_data.warn_notices > 0
            }
        }
    }
    
    path = report_manager.generate_battlecard(comp_dict)
    
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"battlecard_{comp.name.replace(' ', '_').lower()}.pdf"
    )


@router.get("/api/reports/comparison")
async def generate_comparison_report():
    """Generate and return comparison report PDF."""
    from database import SessionLocal, Competitor
    # Only essentials for comparison to avoid timeout
    from google_ecosystem_scraper import GoogleEcosystemScraper
    from seo_scraper import SEOScraper
    
    db = SessionLocal()
    competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False,
        Competitor.threat_level.in_(["High", "Medium"])
    ).all()
    db.close()
    
    google = GoogleEcosystemScraper()
    seo = SEOScraper()

    comp_dicts = []
    
    for c in competitors:
        # Lite fetch
        google_data = google.get_ecosystem_data(c.name)
        seo_data = seo.get_seo_data(c.name)
        
        comp_dicts.append({
            "name": c.name,
            "threat_level": c.threat_level,
            "pricing_model": c.pricing_model,
            "base_price": c.base_price,
            "customer_count": c.customer_count,
            "employee_count": c.employee_count,
            "g2_rating": c.g2_rating,
            "target_segments": c.target_segments,
            "funding_total": c.funding_total,
            "product_categories": c.product_categories,
            "deep_dive": {
                "digital": {
                    "ads_active": google_data.ads.active_creative_count,
                    "brand_index": google_data.trends.current_index
                },
                "seo": {
                    "da": seo_data.domain_authority
                }
            }
        })
    
    path = report_manager.generate_comparison(comp_dicts)
    
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"certify_intel_comparison_{datetime.now().strftime('%Y%m%d')}.pdf"
    )


# ============== Rate Limiting Middleware ==============

async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to requests."""
    client_ip = request.client.host
    
    if not rate_limiter.is_allowed(client_ip):
        return HTMLResponse(
            content='{"error": "Rate limit exceeded"}',
            status_code=429,
            media_type="application/json"
        )
    
    response = await call_next(request)
    
    # Add rate limit headers
    remaining = rate_limiter.get_remaining(client_ip)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.limit)
    
    return response


# ============== Settings Endpoints ==============

class ThreatCriteriaUpdate(BaseModel):
    high_threat_criteria: str
    medium_threat_criteria: str
    low_threat_criteria: str

def background_classification_task():
    """Background task to re-run classification."""
    db = SessionLocal()
    try:
        print("Starting background re-classification based on new criteria...")
        workflow = ClassificationWorkflow(db)
        workflow.run_classification_pipeline()
        print("Background re-classification complete.")
    except Exception as e:
        print(f"Error in background classification: {e}")
    finally:
        db.close()

@router.get("/api/settings/threat-criteria")
async def get_threat_criteria(db: Session = Depends(get_db)):
    """Get current threat level classification criteria."""
    criteria = {
        "high": "Direct competitor with overlapping products, >$10M revenue, or rapid growth.",
        "medium": "Partial product overlap or emerging competitor in adjacent market.",
        "low": "Indirect competitor, legacy system, or different market focus."
    }
    
    settings = db.query(SystemSetting).filter(SystemSetting.key.in_([
        "threat_criteria_high", "threat_criteria_medium", "threat_criteria_low"
    ])).all()
    
    for s in settings:
        if s.key == "threat_criteria_high": criteria["high"] = s.value
        elif s.key == "threat_criteria_medium": criteria["medium"] = s.value
        elif s.key == "threat_criteria_low": criteria["low"] = s.value
        
    return criteria

@router.post("/api/settings/threat-criteria")
async def update_threat_criteria(update: ThreatCriteriaUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Update threat level criteria and trigger re-classification."""
    
    def upsert(key, value):
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not setting:
            setting = SystemSetting(key=key, value=value)
            db.add(setting)
        else:
            setting.value = value
            setting.updated_at = datetime.utcnow()
    
    upsert("threat_criteria_high", update.high_threat_criteria)
    upsert("threat_criteria_medium", update.medium_threat_criteria)
    upsert("threat_criteria_low", update.low_threat_criteria)
    
    db.commit()
    
    # Trigger re-classification
    background_tasks.add_task(background_classification_task)
    
    return {"status": "updated", "message": "Criteria updated. AI classification has been triggered."}

