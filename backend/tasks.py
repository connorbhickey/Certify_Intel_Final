"""
Certify Intel - Celery Tasks
Background tasks for data collection, notifications, and scheduling.
"""
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import func

from celery_app import celery_app

# Ensure backend is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============== Scraping Tasks ==============

@celery_app.task(bind=True, max_retries=3)
def scrape_competitor(self, competitor_id: int) -> Dict[str, Any]:
    """
    Scrape a single competitor's website for updated data.
    
    Args:
        competitor_id: Database ID of the competitor to scrape.
        
    Returns:
        Dict with scrape results and updated fields.
    """
    try:
        from main import SessionLocal, Competitor
        from scraper import CompetitorScraper
        
        db = SessionLocal()
        competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
        
        if not competitor:
            return {"error": "Competitor not found", "id": competitor_id}
        
        scraper = CompetitorScraper()
        result = scraper.scrape_competitor(competitor.website)
        
        # Update competitor record
        updates = []
        if result.get("pricing"):
            competitor.base_price = result["pricing"]
            updates.append("base_price")
        if result.get("features"):
            competitor.key_features = result["features"]
            updates.append("key_features")
        if result.get("employee_count"):
            competitor.employee_count = result["employee_count"]
            updates.append("employee_count")
            
        competitor.last_updated = datetime.utcnow()
        db.commit()
        db.close()
        
        return {
            "success": True,
            "competitor_id": competitor_id,
            "competitor_name": competitor.name,
            "updates": updates,
            "scraped_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        return {"error": str(e), "competitor_id": competitor_id}


@celery_app.task(bind=True)
def scrape_all_competitors(self) -> Dict[str, Any]:
    """
    Trigger scraping for all active competitors.
    
    Returns:
        Dict with task IDs for each competitor scrape.
    """
    try:
        from main import SessionLocal, Competitor
        
        db = SessionLocal()
        competitors = db.query(Competitor).filter(
            Competitor.is_deleted == False,
            Competitor.status == "Active"
        ).all()
        db.close()
        
        task_ids = []
        for comp in competitors:
            task = scrape_competitor.delay(comp.id)
            task_ids.append({"competitor_id": comp.id, "task_id": task.id})
        
        return {
            "success": True,
            "total_competitors": len(competitors),
            "tasks_queued": len(task_ids),
            "task_ids": task_ids
        }
        
    except Exception as e:
        return {"error": str(e)}


# ============== Discovery Tasks ==============

@celery_app.task(bind=True, time_limit=300)
def run_discovery(self, use_live: bool = False, max_candidates: int = 10) -> Dict[str, Any]:
    """
    Run the autonomous competitor discovery agent.
    
    Args:
        use_live: Whether to use live DuckDuckGo search.
        max_candidates: Maximum candidates to return.
        
    Returns:
        Dict with discovered candidates.
    """
    import asyncio
    
    try:
        from discovery_agent import DiscoveryAgent
        
        agent = DiscoveryAgent(use_live_search=use_live, use_openai=False)
        
        # Run async discovery in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        candidates = loop.run_until_complete(agent.run_discovery_loop(max_candidates))
        loop.close()
        
        return {
            "success": True,
            "candidates": candidates,
            "count": len(candidates),
            "mode": "live" if use_live else "seed",
            "discovered_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e), "candidates": []}


# ============== Notification Tasks ==============

@celery_app.task(bind=True)
def send_email_alert(self, subject: str, body_html: str, recipients: List[str] = None) -> Dict[str, Any]:
    """
    Send an email alert.
    
    Args:
        subject: Email subject line.
        body_html: HTML body content.
        recipients: Optional list of email recipients.
        
    Returns:
        Dict with send status.
    """
    try:
        from alerts import AlertSystem
        
        alert_system = AlertSystem()
        
        if recipients:
            alert_system.config.to_emails = recipients
            
        success = alert_system.send_alert(subject, body_html)
        
        return {
            "success": success,
            "subject": subject,
            "recipients": alert_system.config.to_emails,
            "sent_at": datetime.utcnow().isoformat() if success else None
        }
        
    except Exception as e:
        return {"error": str(e), "success": False}


@celery_app.task(bind=True)
def send_daily_digest(self) -> Dict[str, Any]:
    """
    Send the daily change digest email.
    
    Returns:
        Dict with send status.
    """
    try:
        from alerts import send_daily_digest as _send_digest
        
        success = _send_digest()
        
        return {
            "success": success,
            "type": "daily_digest",
            "sent_at": datetime.utcnow().isoformat() if success else None
        }
        
    except Exception as e:
        return {"error": str(e), "success": False}


@celery_app.task(bind=True)
def send_weekly_summary(self) -> Dict[str, Any]:
    """
    Send the weekly summary email.
    
    Returns:
        Dict with send status.
    """
    try:
        from alerts import send_weekly_summary as _send_summary
        
        success = _send_summary()
        
        return {
            "success": success,
            "type": "weekly_summary",
            "sent_at": datetime.utcnow().isoformat() if success else None
        }
        
    except Exception as e:
        return {"error": str(e), "success": False}


# ============== Scheduled Tasks ==============

@celery_app.task(bind=True)
def weekly_refresh(self) -> Dict[str, Any]:
    """
    Weekly full data refresh - scrapes all competitors and sends summary.
    
    Returns:
        Dict with refresh results.
    """
    try:
        # Trigger all competitor scrapes
        scrape_result = scrape_all_competitors.delay()
        
        # Send weekly summary after scraping (delay by 30 minutes)
        send_weekly_summary.apply_async(countdown=1800)
        
        return {
            "success": True,
            "scrape_task_id": scrape_result.id,
            "type": "weekly_refresh",
            "triggered_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}


@celery_app.task(bind=True)
def check_high_priority(self) -> Dict[str, Any]:
    """
    Daily check of high-threat competitors for changes.
    
    Returns:
        Dict with check results.
    """
    try:
        from main import SessionLocal, Competitor
        
        db = SessionLocal()
        high_threat = db.query(Competitor).filter(
            Competitor.is_deleted == False,
            func.upper(Competitor.threat_level) == "HIGH"
        ).all()
        db.close()
        
        task_ids = []
        for comp in high_threat:
            task = scrape_competitor.delay(comp.id)
            task_ids.append({"competitor_id": comp.id, "task_id": task.id})
        
        return {
            "success": True,
            "high_priority_count": len(high_threat),
            "tasks_queued": len(task_ids),
            "type": "daily_high_priority",
            "triggered_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}


# ============== Report Tasks ==============

@celery_app.task(bind=True)
def generate_weekly_briefing(self) -> Dict[str, Any]:
    """
    Generate the weekly executive briefing PDF.
    
    Returns:
        Dict with file path.
    """
    try:
        from main import SessionLocal, Competitor
        from reports import ReportManager
        
        db = SessionLocal()
        competitors = db.query(Competitor).filter(Competitor.is_deleted == False).all()
        db.close()
        
        manager = ReportManager("./exports")
        filepath = manager.generate_weekly_briefing([c.__dict__ for c in competitors])
        
        return {
            "success": True,
            "filepath": filepath,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}


# ============== Utility Tasks ==============

@celery_app.task
def health_check() -> Dict[str, Any]:
    """
    Simple health check task to verify Celery is working.
    
    Returns:
        Dict with status.
    """
    return {
        "status": "healthy",
        "worker": "celery",
        "timestamp": datetime.utcnow().isoformat()
    }
