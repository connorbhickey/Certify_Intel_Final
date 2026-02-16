"""
Certify Intel - Notification Integrations
Slack, Microsoft Teams, SMS (Twilio), and custom alert rules
"""
import os
import json
import httpx
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


# ============== Slack Integration ==============

class SlackNotifier:
    """Sends notifications to Slack channels."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    
    async def send_message(self, message: str, channel: Optional[str] = None) -> bool:
        """Send a simple text message to Slack."""
        if not self.webhook_url:
            print("Slack webhook not configured")
            return False
        
        payload = {"text": message}
        if channel:
            payload["channel"] = channel
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code == 200
        except Exception as e:
            print(f"Slack notification failed: {e}")
            return False
    
    async def send_competitor_alert(self, competitor_name: str, changes: List[Dict]) -> bool:
        """Send a formatted competitor change alert to Slack."""
        if not self.webhook_url:
            return False
        
        # Build Slack blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔔 Competitor Alert: {competitor_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{len(changes)} changes detected*"
                }
            },
            {"type": "divider"}
        ]
        
        for change in changes[:5]:  # Limit to 5 changes
            severity_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🔵"}.get(change.get("severity"), "⚪")
            blocks.append({
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:* {change.get('change_type')}"},
                    {"type": "mrkdwn", "text": f"*Severity:* {severity_emoji} {change.get('severity')}"},
                    {"type": "mrkdwn", "text": f"*Previous:* {change.get('previous_value', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*New:* {change.get('new_value', 'N/A')}"},
                ]
            })
        
        if len(changes) > 5:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"_...and {len(changes) - 5} more changes_"}
            })
        
        payload = {"blocks": blocks}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code == 200
        except Exception as e:
            print(f"Slack notification failed: {e}")
            return False
    
    async def send_weekly_summary(self, stats: Dict[str, Any]) -> bool:
        """Send weekly summary to Slack."""
        if not self.webhook_url:
            return False
        
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Weekly Competitive Intelligence Summary", "emoji": True}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Competitors:* {stats.get('total_competitors', 0)}"},
                    {"type": "mrkdwn", "text": f"*High Threat:* {stats.get('high_threat', 0)}"},
                    {"type": "mrkdwn", "text": f"*Changes This Week:* {stats.get('changes', 0)}"},
                    {"type": "mrkdwn", "text": f"*Active:* {stats.get('active', 0)}"},
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Dashboard"},
                        "url": "http://localhost:8000/api/dashboard/stats"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Download Report"},
                        "url": "http://localhost:8000/api/export/excel"
                    }
                ]
            }
        ]
        
        payload = {"blocks": blocks}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code == 200
        except Exception as e:
            print(f"Slack notification failed: {e}")
            return False


# ============== Microsoft Teams Integration ==============

class TeamsNotifier:
    """Sends notifications to Microsoft Teams channels."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("TEAMS_WEBHOOK_URL")
    
    async def send_message(self, message: str) -> bool:
        """Send a simple message to Teams."""
        if not self.webhook_url:
            print("Teams webhook not configured")
            return False
        
        # Adaptive Card format for Teams
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": "Certify Intel Alert",
            "text": message
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code == 200
        except Exception as e:
            print(f"Teams notification failed: {e}")
            return False
    
    async def send_competitor_alert(self, competitor_name: str, changes: List[Dict]) -> bool:
        """Send formatted competitor alert to Teams."""
        if not self.webhook_url:
            return False
        
        sections = []
        for change in changes[:5]:
            severity_color = {"High": "attention", "Medium": "warning", "Low": "good"}.get(change.get("severity"), "default")
            sections.append({
                "activityTitle": f"{change.get('change_type')}",
                "facts": [
                    {"name": "Previous", "value": str(change.get('previous_value', 'N/A'))},
                    {"name": "New", "value": str(change.get('new_value', 'N/A'))},
                    {"name": "Severity", "value": change.get('severity', 'Unknown')}
                ]
            })
        
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FF0000" if any(c.get("severity") == "High" for c in changes) else "FFA500",
            "summary": f"Competitor Alert: {competitor_name}",
            "title": f"🔔 Competitor Alert: {competitor_name}",
            "sections": sections,
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "View Dashboard",
                    "targets": [{"os": "default", "uri": "http://localhost:8000"}]
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code == 200
        except Exception as e:
            print(f"Teams notification failed: {e}")
            return False


# ============== SMS Alerts (Twilio) ==============

class SMSNotifier:
    """Sends SMS alerts via Twilio."""
    
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None
    ):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_FROM_NUMBER")
        self.to_numbers = self._parse_recipients()
    
    def _parse_recipients(self) -> List[str]:
        """Parse SMS recipient numbers from env."""
        numbers = os.getenv("SMS_ALERT_NUMBERS", "")
        return [n.strip() for n in numbers.split(",") if n.strip()]
    
    async def send_sms(self, message: str, to_number: Optional[str] = None) -> bool:
        """Send an SMS message."""
        if not all([self.account_sid, self.auth_token, self.from_number]):
            print("Twilio not configured")
            return False
        
        recipients = [to_number] if to_number else self.to_numbers
        if not recipients:
            print("No SMS recipients configured")
            return False
        
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        
        success = True
        async with httpx.AsyncClient() as client:
            for recipient in recipients:
                try:
                    response = await client.post(
                        url,
                        auth=(self.account_sid, self.auth_token),
                        data={
                            "From": self.from_number,
                            "To": recipient,
                            "Body": message[:1600]  # SMS limit
                        }
                    )
                    if response.status_code not in [200, 201]:
                        print(f"SMS to {recipient} failed: {response.text}")
                        success = False
                except Exception as e:
                    print(f"SMS failed: {e}")
                    success = False
        
        return success
    
    async def send_critical_alert(self, competitor_name: str, change_type: str, new_value: str) -> bool:
        """Send a critical change alert via SMS."""
        message = f"🚨 CERTIFY INTEL ALERT\n{competitor_name}: {change_type} changed to {new_value}"
        return await self.send_sms(message)


# ============== Custom Alert Rules ==============

@dataclass
class AlertRule:
    """Custom alert rule definition."""
    id: str
    name: str
    competitor: Optional[str]  # None for all competitors
    field: str  # Field to monitor
    condition: str  # "changed", "contains", "greater_than", "less_than"
    value: Optional[str]  # Value for comparison
    severity: str  # High, Medium, Low
    channels: List[str]  # ["email", "slack", "teams", "sms"]
    active: bool = True


class AlertRuleEngine:
    """Evaluates custom alert rules."""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self._load_rules()
    
    def _load_rules(self):
        """Load rules from config file or database."""
        # Default rules
        self.rules = [
            AlertRule(
                id="pricing_change",
                name="Pricing Change Alert",
                competitor=None,
                field="base_price",
                condition="changed",
                value=None,
                severity="High",
                channels=["email", "slack"]
            ),
            AlertRule(
                id="funding_announcement",
                name="New Funding Alert",
                competitor=None,
                field="funding_total",
                condition="changed",
                value=None,
                severity="High",
                channels=["email", "slack", "sms"]
            ),
            AlertRule(
                id="phreesia_monitoring",
                name="Phreesia Any Change",
                competitor="Phreesia",
                field="*",
                condition="changed",
                value=None,
                severity="Medium",
                channels=["slack"]
            ),
            AlertRule(
                id="g2_rating_drop",
                name="G2 Rating Decrease",
                competitor=None,
                field="g2_rating",
                condition="less_than",
                value="previous",
                severity="Medium",
                channels=["email"]
            ),
        ]
    
    def evaluate(self, competitor_name: str, field: str, old_value: Any, new_value: Any) -> List[AlertRule]:
        """Evaluate which rules match a change."""
        matched_rules = []
        
        for rule in self.rules:
            if not rule.active:
                continue
            
            # Check competitor filter
            if rule.competitor and rule.competitor.lower() != competitor_name.lower():
                continue
            
            # Check field filter
            if rule.field != "*" and rule.field != field:
                continue
            
            # Check condition
            if self._check_condition(rule, old_value, new_value):
                matched_rules.append(rule)
        
        return matched_rules
    
    def _check_condition(self, rule: AlertRule, old_value: Any, new_value: Any) -> bool:
        """Check if a rule condition is met."""
        if rule.condition == "changed":
            return old_value != new_value
        elif rule.condition == "contains":
            return rule.value and rule.value.lower() in str(new_value).lower()
        elif rule.condition == "greater_than":
            try:
                return float(new_value) > float(rule.value)
            except:
                return False
        elif rule.condition == "less_than":
            if rule.value == "previous":
                try:
                    return float(new_value) < float(old_value)
                except:
                    return False
            try:
                return float(new_value) < float(rule.value)
            except:
                return False
        return False
    
    def add_rule(self, rule: AlertRule):
        """Add a new rule."""
        self.rules.append(rule)
    
    def remove_rule(self, rule_id: str):
        """Remove a rule by ID."""
        self.rules = [r for r in self.rules if r.id != rule_id]
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all rules as dicts."""
        return [asdict(r) for r in self.rules]


# ============== Unified Notification Manager ==============

from alerts import AlertSystem

class NotificationManager:
    """Manages all notification channels."""
    
    def __init__(self):
        self.slack = SlackNotifier()
        self.teams = TeamsNotifier()
        self.sms = SMSNotifier()
        self.email = AlertSystem()
        self.rule_engine = AlertRuleEngine()
    
    async def process_change(
        self, 
        competitor_name: str, 
        field: str, 
        old_value: Any, 
        new_value: Any
    ):
        """Process a change and send appropriate notifications."""
        matched_rules = self.rule_engine.evaluate(competitor_name, field, old_value, new_value)
        
        for rule in matched_rules:
            change_data = {
                "competitor": competitor_name,
                "change_type": field.replace("_", " ").title(),
                "previous_value": old_value,
                "new_value": new_value,
                "severity": rule.severity
            }
            
            # Send to configured channels
            if "slack" in rule.channels:
                await self.slack.send_competitor_alert(competitor_name, [change_data])
            
            if "teams" in rule.channels:
                await self.teams.send_competitor_alert(competitor_name, [change_data])
            
            if "email" in rule.channels:
                 # Note: AlertSystem.send_change_alert expects ChangeLog objects, 
                 # but here we have a dict. We'll use the raw send_alert for now.
                 subject = f"🔔 Certify Intel Alert: {competitor_name} - {change_data['change_type']}"
                 body = f"Change detected for {competitor_name}.\nType: {change_data['change_type']}\nNew Value: {new_value}"
                 self.email.send_alert(subject, body, body)

            if "sms" in rule.channels and rule.severity == "High":
                await self.sms.send_critical_alert(
                    competitor_name, 
                    field.replace("_", " ").title(),
                    str(new_value)
                )
    
    async def send_to_all_channels(self, message: str):
        """Send a message to all configured channels."""
        await self.slack.send_message(message)
        await self.teams.send_message(message)
        self.email.send_alert("Certify Intel Notification", message, message)
    
    def get_alert_rules(self) -> List[Dict[str, Any]]:
        """Get all configured alert rules."""
        return self.rule_engine.get_rules()
    
    def add_alert_rule(self, rule_data: Dict[str, Any]) -> AlertRule:
        """Add a new custom alert rule."""
        rule = AlertRule(**rule_data)
        self.rule_engine.add_rule(rule)
        return rule


# Test function
async def test_notifications():
    """Test notification system."""
    manager = NotificationManager()
    
    # Test rule evaluation
    rules = manager.rule_engine.evaluate("Phreesia", "base_price", "$3.00", "$3.50")
    print(f"Matched rules: {[r.name for r in rules]}")
    
    # Test Slack message (will fail without webhook)
    await manager.slack.send_message("Test message from Certify Intel")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_notifications())
