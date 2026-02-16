"""
Certify Intel - Email Alert System
Sends email alerts for critical competitor changes.
Supports TEST_EMAIL_MODE for development/demo without real email credentials.
"""
from __future__ import annotations

import os
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Optional, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path

if TYPE_CHECKING:
    from database import ChangeLog

# Test email mode - logs emails instead of sending
TEST_EMAIL_MODE = os.getenv("TEST_EMAIL_MODE", "true").lower() in ("true", "1", "yes")
EMAIL_LOG_FILE = Path(__file__).parent / "email_log.json"


@dataclass
class AlertConfig:
    """Email alert configuration."""
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    from_email: str = os.getenv("ALERT_FROM_EMAIL", "alerts@certifyintel.local")
    to_emails: List[str] = None
    test_mode: bool = TEST_EMAIL_MODE

    def __post_init__(self):
        if self.to_emails is None:
            to_list = os.getenv("ALERT_TO_EMAILS", "demo@certifyintel.local")
            self.to_emails = [e.strip() for e in to_list.split(",") if e.strip()]


def log_test_email(subject: str, body_html: str, from_email: str, to_emails: List[str]):
    """Log email to file instead of sending (for test mode)."""
    email_record = {
        "timestamp": datetime.utcnow().isoformat(),
        "subject": subject,
        "from": from_email,
        "to": to_emails,
        "body_preview": body_html[:500] + "..." if len(body_html) > 500 else body_html,
        "status": "logged_test_mode"
    }

    # Load existing log
    log_data = []
    if EMAIL_LOG_FILE.exists():
        try:
            with open(EMAIL_LOG_FILE, 'r') as f:
                log_data = json.load(f)
        except:
            log_data = []

    # Append new email (keep last 50)
    log_data.append(email_record)
    log_data = log_data[-50:]

    # Save log
    with open(EMAIL_LOG_FILE, 'w') as f:
        json.dump(log_data, f, indent=2)

    print(f"[TEST MODE] Email logged: {subject}")
    return True


class AlertSystem:
    """Manages email alerts for competitor changes."""

    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()

    def send_alert(self, subject: str, body_html: str, body_text: str = None) -> bool:
        """Send an email alert (or log in test mode)."""

        # TEST MODE: Log instead of sending
        if self.config.test_mode or TEST_EMAIL_MODE:
            return log_test_email(subject, body_html, self.config.from_email, self.config.to_emails)

        # PRODUCTION MODE: Actually send email
        if not self.config.smtp_user or not self.config.to_emails:
            print("Email not configured. Skipping alert.")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.from_email
            msg["To"] = ", ".join(self.config.to_emails)

            # Add text and HTML parts
            if body_text:
                msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            # Send email
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(
                    self.config.from_email,
                    self.config.to_emails,
                    msg.as_string()
                )

            print(f"Alert sent: {subject}")
            return True

        except Exception as e:
            print(f"Failed to send alert: {e}")
            return False
    
    def send_change_alert(self, changes: List['ChangeLog']) -> bool:  # noqa: F821
        """Send alert for detected changes."""
        if not changes:
            return False
        
        # Group by severity
        high_severity = [c for c in changes if c.severity == "High"]
        medium_severity = [c for c in changes if c.severity == "Medium"]
        low_severity = [c for c in changes if c.severity == "Low"]
        
        # Build subject
        subject = f"🔔 Certify Intel: {len(changes)} Competitor Changes Detected"
        if high_severity:
            subject += f" ({len(high_severity)} Critical)"
        
        # Build HTML body
        html = self._build_change_email_html(changes, high_severity, medium_severity, low_severity)
        
        return self.send_alert(subject, html)
    
    def send_daily_digest(self) -> bool:
        """Send daily digest of changes from last 24 hours."""
        from main import SessionLocal, ChangeLog  # Local import
        
        db = SessionLocal()
        
        yesterday = datetime.utcnow() - timedelta(days=1)
        changes = db.query(ChangeLog).filter(
            ChangeLog.detected_at >= yesterday
        ).order_by(ChangeLog.detected_at.desc()).all()
        
        db.close()
        
        if not changes:
            print("No changes in last 24 hours. Skipping digest.")
            return False
        
        # Group by severity
        high_severity = [c for c in changes if c.severity == "High"]
        medium_severity = [c for c in changes if c.severity == "Medium"]
        low_severity = [c for c in changes if c.severity == "Low"]
        
        subject = f"📊 Certify Intel Daily Digest - {datetime.now().strftime('%B %d, %Y')}"
        
        html = self._build_digest_email_html(changes, high_severity, medium_severity, low_severity)
        
        return self.send_alert(subject, html)
    
    def send_weekly_summary(self) -> bool:
        """Send weekly summary email."""
        from main import SessionLocal, ChangeLog, Competitor  # Local import
        
        db = SessionLocal()
        
        last_week = datetime.utcnow() - timedelta(days=7)
        changes = db.query(ChangeLog).filter(
            ChangeLog.detected_at >= last_week
        ).order_by(ChangeLog.detected_at.desc()).all()
        
        # Get competitor stats
        competitors = db.query(Competitor).filter(Competitor.is_deleted == False).all()
        
        db.close()
        
        stats = {
            "total": len(competitors),
            "high_threat": len([c for c in competitors if c.threat_level and c.threat_level.upper() == "HIGH"]),
            "medium_threat": len([c for c in competitors if c.threat_level and c.threat_level.upper() == "MEDIUM"]),
            "low_threat": len([c for c in competitors if c.threat_level and c.threat_level.upper() == "LOW"]),
            "changes": len(changes),
        }
        
        subject = f"📈 Certify Intel Weekly Summary - Week of {datetime.now().strftime('%B %d, %Y')}"
        
        html = self._build_weekly_summary_html(stats, changes)
        
        return self.send_alert(subject, html)
    
    def _build_change_email_html(self, all_changes, high, medium, low) -> str:
        """Build HTML for change alert email."""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #2F5496; color: white; padding: 20px; border-radius: 8px; }}
                .section {{ margin: 20px 0; padding: 15px; border-radius: 8px; }}
                .high {{ background: #FFE6E6; border-left: 4px solid #DC3545; }}
                .medium {{ background: #FFF3E6; border-left: 4px solid #FFC107; }}
                .low {{ background: #E6F3FF; border-left: 4px solid #17A2B8; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #f5f5f5; }}
                .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
                .badge-high {{ background: #DC3545; color: white; }}
                .badge-medium {{ background: #FFC107; color: black; }}
                .badge-low {{ background: #17A2B8; color: white; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔔 Competitor Changes Detected</h1>
                <p>Certify Intel has detected {len(all_changes)} changes in competitor data.</p>
            </div>
        """
        
        if high:
            html += self._build_change_section("🚨 High Priority Changes", high, "high")
        if medium:
            html += self._build_change_section("⚠️ Medium Priority Changes", medium, "medium")
        if low:
            html += self._build_change_section("ℹ️ Low Priority Changes", low, "low")
        
        html += """
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This is an automated alert from Certify Intel. 
                <a href="http://localhost:8000/api/export/excel">Download latest Excel export</a>
            </p>
        </body>
        </html>
        """
        
        return html
    
    def _build_change_section(self, title: str, changes: List['ChangeLog'], severity: str) -> str:  # noqa: F821
        """Build HTML section for a change category."""
        html = f"""
        <div class="section {severity}">
            <h2>{title}</h2>
            <table>
                <tr>
                    <th>Competitor</th>
                    <th>Change Type</th>
                    <th>Previous</th>
                    <th>New</th>
                    <th>Detected</th>
                </tr>
        """
        
        for change in changes[:10]:  # Limit to 10 per section
            html += f"""
                <tr>
                    <td><strong>{change.competitor_name}</strong></td>
                    <td>{change.change_type}</td>
                    <td>{change.previous_value or '-'}</td>
                    <td>{change.new_value}</td>
                    <td>{change.detected_at.strftime('%Y-%m-%d %H:%M')}</td>
                </tr>
            """
        
        if len(changes) > 10:
            html += f"""
                <tr>
                    <td colspan="5" style="text-align: center; color: #666;">
                        ... and {len(changes) - 10} more changes
                    </td>
                </tr>
            """
        
        html += """
            </table>
        </div>
        """
        
        return html
    
    def _build_digest_email_html(self, all_changes, high, medium, low) -> str:
        """Build HTML for daily digest email."""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #2F5496; color: white; padding: 20px; border-radius: 8px; }}
                .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
                .stat-card {{ background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center; flex: 1; }}
                .stat-number {{ font-size: 32px; font-weight: bold; color: #2F5496; }}
                .stat-label {{ color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Daily Digest</h1>
                <p>{datetime.now().strftime('%B %d, %Y')}</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{len(all_changes)}</div>
                    <div class="stat-label">Total Changes</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #DC3545;">{len(high)}</div>
                    <div class="stat-label">High Priority</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #FFC107;">{len(medium)}</div>
                    <div class="stat-label">Medium Priority</div>
                </div>
            </div>
        """
        
        if high:
            html += self._build_change_section("🚨 High Priority Changes", high, "high")
        if medium:
            html += self._build_change_section("⚠️ Medium Priority Changes", medium, "medium")
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def _build_weekly_summary_html(self, stats: dict, changes: List['ChangeLog']) -> str:  # noqa: F821
        """Build HTML for weekly summary email."""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #2F5496; color: white; padding: 20px; border-radius: 8px; }}
                .stats {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
                .stat-card {{ background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center; min-width: 120px; }}
                .stat-number {{ font-size: 32px; font-weight: bold; color: #2F5496; }}
                .stat-label {{ color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📈 Weekly Summary</h1>
                <p>Week of {datetime.now().strftime('%B %d, %Y')}</p>
            </div>
            
            <h2>Competitor Overview</h2>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{stats['total']}</div>
                    <div class="stat-label">Total Competitors</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #DC3545;">{stats['high_threat']}</div>
                    <div class="stat-label">High Threat</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #FFC107;">{stats['medium_threat']}</div>
                    <div class="stat-label">Medium Threat</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #17A2B8;">{stats['low_threat']}</div>
                    <div class="stat-label">Low Threat</div>
                </div>
            </div>
            
            <h2>Weekly Activity</h2>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{stats['changes']}</div>
                    <div class="stat-label">Changes Detected</div>
                </div>
            </div>
            
            <p style="color: #666; margin-top: 30px;">
                <a href="http://localhost:8000/api/export/excel">📥 Download Latest Excel Export</a>
            </p>
        </body>
        </html>
        """
        
        return html


# Quick send functions

def send_immediate_alert(changes: List['ChangeLog']) -> bool:  # noqa: F821
    """Send an immediate alert for critical changes."""
    alert_system = AlertSystem()
    return alert_system.send_change_alert(changes)


def send_daily_digest() -> bool:
    """Send daily digest email."""
    alert_system = AlertSystem()
    return alert_system.send_daily_digest()


def send_weekly_summary() -> bool:
    """Send weekly summary email."""
    alert_system = AlertSystem()
    return alert_system.send_weekly_summary()


if __name__ == "__main__":
    # Test alert system
    print("Testing alert system...")
    alert_system = AlertSystem()
    
    # Check configuration
    print(f"SMTP Host: {alert_system.config.smtp_host}")
    print(f"SMTP User: {alert_system.config.smtp_user or 'Not configured'}")
    print(f"Recipients: {alert_system.config.to_emails or 'Not configured'}")
    
    if not alert_system.config.smtp_user:
        print("\nTo enable email alerts, set these environment variables:")
        print("  SMTP_HOST=smtp.gmail.com")
        print("  SMTP_PORT=587")
        print("  SMTP_USER=your-email@gmail.com")
        print("  SMTP_PASSWORD=your-app-password")
        print("  ALERT_TO_EMAILS=recipient1@example.com,recipient2@example.com")
