"""
Certify Intel - Webhook Manager
Outbound webhook system for real-time integrations.
"""
import os
import json
import hashlib
import hmac
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
import urllib.request
import urllib.error
import threading


@dataclass
class Webhook:
    """Webhook configuration."""
    id: str
    url: str
    events: List[str]
    secret: Optional[str]
    active: bool
    created_at: str
    last_triggered: Optional[str]
    failure_count: int


@dataclass
class WebhookEvent:
    """Event to be sent to webhooks."""
    event_type: str
    payload: Dict[str, Any]
    timestamp: str
    source: str


class WebhookManager:
    """Manages outbound webhooks for real-time notifications."""
    
    # Available event types
    EVENT_TYPES = [
        "competitor.created",
        "competitor.updated",
        "competitor.deleted",
        "price.changed",
        "threat_level.changed",
        "news.alert",
        "discovery.new_candidate",
        "deal.won",
        "deal.lost",
        "weekly.summary"
    ]
    
    def __init__(self):
        self._webhooks: Dict[str, Webhook] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._load_webhooks()
    
    def _load_webhooks(self):
        """Load webhooks from storage."""
        # In production, load from database
        # For now, check for environment-configured webhooks
        
        slack_url = os.getenv("SLACK_WEBHOOK_URL")
        if slack_url:
            self._webhooks["slack_default"] = Webhook(
                id="slack_default",
                url=slack_url,
                events=["price.changed", "threat_level.changed", "news.alert"],
                secret=None,
                active=True,
                created_at=datetime.utcnow().isoformat(),
                last_triggered=None,
                failure_count=0
            )
        
        teams_url = os.getenv("TEAMS_WEBHOOK_URL")
        if teams_url:
            self._webhooks["teams_default"] = Webhook(
                id="teams_default",
                url=teams_url,
                events=["price.changed", "threat_level.changed", "news.alert"],
                secret=None,
                active=True,
                created_at=datetime.utcnow().isoformat(),
                last_triggered=None,
                failure_count=0
            )
    
    def register_webhook(self, 
                        url: str, 
                        events: List[str],
                        secret: Optional[str] = None) -> Webhook:
        """
        Register a new webhook.
        
        Args:
            url: Webhook endpoint URL
            events: List of event types to subscribe to
            secret: Optional secret for HMAC signatures
            
        Returns:
            Created Webhook object
        """
        # Validate events
        invalid_events = [e for e in events if e not in self.EVENT_TYPES]
        if invalid_events:
            raise ValueError(f"Invalid event types: {invalid_events}")
        
        # Generate ID
        webhook_id = hashlib.md5(f"{url}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:12]
        
        webhook = Webhook(
            id=webhook_id,
            url=url,
            events=events,
            secret=secret,
            active=True,
            created_at=datetime.utcnow().isoformat(),
            last_triggered=None,
            failure_count=0
        )
        
        self._webhooks[webhook_id] = webhook
        return webhook
    
    def unregister_webhook(self, webhook_id: str) -> bool:
        """
        Unregister a webhook.
        
        Args:
            webhook_id: ID of webhook to remove
            
        Returns:
            True if removed, False if not found
        """
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            return True
        return False
    
    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all registered webhooks."""
        return [asdict(w) for w in self._webhooks.values()]
    
    def trigger(self, event_type: str, payload: Dict[str, Any], async_send: bool = True):
        """
        Trigger a webhook event.
        
        Args:
            event_type: Type of event
            payload: Event payload
            async_send: Whether to send asynchronously
        """
        if event_type not in self.EVENT_TYPES:
            print(f"Unknown event type: {event_type}")
            return
        
        event = WebhookEvent(
            event_type=event_type,
            payload=payload,
            timestamp=datetime.utcnow().isoformat(),
            source="certify-intel"
        )
        
        # Find matching webhooks
        matching = [w for w in self._webhooks.values() 
                   if w.active and event_type in w.events]
        
        if not matching:
            return
        
        if async_send:
            # Send in background thread
            thread = threading.Thread(target=self._send_to_all, args=(matching, event))
            thread.daemon = True
            thread.start()
        else:
            self._send_to_all(matching, event)
    
    def _send_to_all(self, webhooks: List[Webhook], event: WebhookEvent):
        """Send event to all matching webhooks."""
        for webhook in webhooks:
            try:
                self._send_webhook(webhook, event)
            except Exception as e:
                print(f"Webhook {webhook.id} failed: {e}")
                webhook.failure_count += 1
                
                # Disable webhook after 5 consecutive failures
                if webhook.failure_count >= 5:
                    webhook.active = False
                    print(f"Webhook {webhook.id} disabled due to repeated failures")
    
    def _send_webhook(self, webhook: Webhook, event: WebhookEvent):
        """Send event to a single webhook."""
        payload = self._format_payload(webhook, event)
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Certify-Intel/1.0"
        }
        
        # Add HMAC signature if secret is configured
        if webhook.secret:
            signature = hmac.new(
                webhook.secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Certify-Signature"] = f"sha256={signature}"
        
        data = json.dumps(payload).encode("utf-8")
        
        req = urllib.request.Request(
            webhook.url,
            data=data,
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.status
                if status >= 200 and status < 300:
                    webhook.last_triggered = datetime.utcnow().isoformat()
                    webhook.failure_count = 0
                else:
                    webhook.failure_count += 1
        except urllib.error.HTTPError as e:
            print(f"Webhook HTTP error: {e.code}")
            webhook.failure_count += 1
            raise
        except urllib.error.URLError as e:
            print(f"Webhook URL error: {e.reason}")
            webhook.failure_count += 1
            raise
    
    def _format_payload(self, webhook: Webhook, event: WebhookEvent) -> Dict[str, Any]:
        """Format payload for webhook destination."""
        # Check if Slack or Teams webhook
        if "slack.com" in webhook.url or "hooks.slack.com" in webhook.url:
            return self._format_slack_payload(event)
        elif "office.com" in webhook.url or "outlook.office" in webhook.url:
            return self._format_teams_payload(event)
        else:
            return self._format_generic_payload(event)
    
    def _format_generic_payload(self, event: WebhookEvent) -> Dict[str, Any]:
        """Format generic webhook payload."""
        return {
            "event": event.event_type,
            "timestamp": event.timestamp,
            "source": event.source,
            "data": event.payload
        }
    
    def _format_slack_payload(self, event: WebhookEvent) -> Dict[str, Any]:
        """Format Slack-specific payload."""
        emoji = self._get_event_emoji(event.event_type)
        color = self._get_event_color(event.event_type)
        
        title = f"{emoji} {self._get_event_title(event.event_type)}"
        
        fields = []
        for key, value in event.payload.items():
            if isinstance(value, (str, int, float)):
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": True
                })
        
        return {
            "attachments": [{
                "color": color,
                "title": title,
                "fields": fields[:10],
                "footer": "Certify Intel",
                "ts": datetime.utcnow().timestamp()
            }]
        }
    
    def _format_teams_payload(self, event: WebhookEvent) -> Dict[str, Any]:
        """Format Microsoft Teams payload."""
        emoji = self._get_event_emoji(event.event_type)
        color = self._get_event_color(event.event_type)
        
        facts = [
            {"name": key.replace("_", " ").title(), "value": str(value)}
            for key, value in event.payload.items()
            if isinstance(value, (str, int, float))
        ]
        
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color.replace("#", ""),
            "summary": self._get_event_title(event.event_type),
            "sections": [{
                "activityTitle": f"{emoji} {self._get_event_title(event.event_type)}",
                "facts": facts[:10],
                "markdown": True
            }]
        }
    
    def _get_event_emoji(self, event_type: str) -> str:
        """Get emoji for event type."""
        emojis = {
            "competitor.created": "➕",
            "competitor.updated": "📝",
            "competitor.deleted": "🗑️",
            "price.changed": "💰",
            "threat_level.changed": "⚠️",
            "news.alert": "📰",
            "discovery.new_candidate": "🔮",
            "deal.won": "🏆",
            "deal.lost": "❌",
            "weekly.summary": "📊"
        }
        return emojis.get(event_type, "📢")
    
    def _get_event_color(self, event_type: str) -> str:
        """Get color for event type."""
        colors = {
            "deal.won": "#28a745",
            "deal.lost": "#dc3545",
            "threat_level.changed": "#ffc107",
            "price.changed": "#17a2b8",
            "news.alert": "#6c757d"
        }
        return colors.get(event_type, "#003087")
    
    def _get_event_title(self, event_type: str) -> str:
        """Get human-readable title for event type."""
        titles = {
            "competitor.created": "New Competitor Added",
            "competitor.updated": "Competitor Updated",
            "competitor.deleted": "Competitor Removed",
            "price.changed": "Price Change Detected",
            "threat_level.changed": "Threat Level Changed",
            "news.alert": "News Alert",
            "discovery.new_candidate": "New Competitor Discovered",
            "deal.won": "Competitive Deal Won",
            "deal.lost": "Competitive Deal Lost",
            "weekly.summary": "Weekly Intelligence Summary"
        }
        return titles.get(event_type, event_type.replace(".", " ").title())
    
    def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """
        Send a test event to a webhook.
        
        Args:
            webhook_id: ID of webhook to test
            
        Returns:
            Dict with test result
        """
        if webhook_id not in self._webhooks:
            return {"success": False, "error": "Webhook not found"}
        
        webhook = self._webhooks[webhook_id]
        
        test_event = WebhookEvent(
            event_type="test",
            payload={
                "message": "This is a test from Certify Intel",
                "timestamp": datetime.utcnow().isoformat()
            },
            timestamp=datetime.utcnow().isoformat(),
            source="certify-intel-test"
        )
        
        try:
            self._send_webhook(webhook, test_event)
            return {"success": True, "message": "Test sent successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
_manager_instance = None

def get_webhook_manager() -> WebhookManager:
    """Get the webhook manager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = WebhookManager()
    return _manager_instance


# Convenience functions for triggering events
def trigger_price_change(competitor_name: str, old_price: str, new_price: str, change_percent: float):
    """Trigger price change webhook."""
    manager = get_webhook_manager()
    manager.trigger("price.changed", {
        "competitor": competitor_name,
        "old_price": old_price,
        "new_price": new_price,
        "change_percent": f"{change_percent:+.1f}%"
    })


def trigger_threat_change(competitor_name: str, old_level: str, new_level: str):
    """Trigger threat level change webhook."""
    manager = get_webhook_manager()
    manager.trigger("threat_level.changed", {
        "competitor": competitor_name,
        "old_level": old_level,
        "new_level": new_level
    })


def trigger_news_alert(competitor_name: str, headline: str, event_type: str):
    """Trigger news alert webhook."""
    manager = get_webhook_manager()
    manager.trigger("news.alert", {
        "competitor": competitor_name,
        "headline": headline,
        "event_type": event_type
    })


def trigger_deal_outcome(competitor_name: str, deal_name: str, value: float, outcome: str):
    """Trigger deal outcome webhook."""
    event_type = "deal.won" if outcome == "Won" else "deal.lost"
    manager = get_webhook_manager()
    manager.trigger(event_type, {
        "competitor": competitor_name,
        "deal_name": deal_name,
        "value": f"${value:,.0f}" if value else "N/A",
        "outcome": outcome
    })


if __name__ == "__main__":
    # Test webhook manager
    manager = WebhookManager()
    
    print("Available event types:", manager.EVENT_TYPES)
    print("Registered webhooks:", manager.list_webhooks())
    
    # Test registration
    webhook = manager.register_webhook(
        url="https://httpbin.org/post",
        events=["price.changed", "threat_level.changed"]
    )
    print(f"Created webhook: {webhook.id}")
    
    # Test trigger (will fail with test URL but demonstrates flow)
    manager.trigger("price.changed", {
        "competitor": "Phreesia",
        "old_price": "$99/month",
        "new_price": "$119/month",
        "change_percent": "+20%"
    }, async_send=False)
