"""
Certify Intel - Price Tracker
Tracks competitor pricing changes and generates alerts.
"""
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PriceChange:
    """Represents a price change event."""
    competitor_id: int
    competitor_name: str
    previous_price: str
    new_price: str
    previous_numeric: Optional[float]
    new_numeric: Optional[float]
    change_percent: Optional[float]
    change_direction: str  # increase, decrease, unchanged
    detected_at: str
    severity: str  # High, Medium, Low


class PriceTracker:
    """Tracks and analyzes competitor pricing changes."""
    
    def __init__(self, db_session=None):
        self.db = db_session
    
    def parse_price(self, price_str: str) -> Optional[float]:
        """
        Extract numeric value from price string.
        
        Examples:
            "$99/month" -> 99.0
            "Contact Sales" -> None
            "$5,000/year" -> 5000.0
        """
        if not price_str:
            return None
        
        price_str = str(price_str).lower()
        
        # Skip non-numeric prices
        if any(x in price_str for x in ["contact", "custom", "free", "n/a", "unknown"]):
            return None
        
        # Extract numbers
        numbers = re.findall(r'[\d,]+(?:\.\d+)?', price_str)
        if not numbers:
            return None
        
        try:
            # Take the first number found
            value = float(numbers[0].replace(',', ''))
            
            # Normalize to monthly if yearly
            if "/year" in price_str or "annual" in price_str:
                value = value / 12
            
            return value
        except:
            return None
    
    def calculate_change(self, old_price: str, new_price: str) -> Tuple[Optional[float], str]:
        """
        Calculate price change percentage and direction.
        
        Returns:
            Tuple of (percent_change, direction)
        """
        old_numeric = self.parse_price(old_price)
        new_numeric = self.parse_price(new_price)
        
        if old_numeric is None or new_numeric is None:
            return None, "unknown"
        
        if old_numeric == 0:
            return None, "unknown"
        
        change_percent = ((new_numeric - old_numeric) / old_numeric) * 100
        
        if change_percent > 0:
            direction = "increase"
        elif change_percent < 0:
            direction = "decrease"
        else:
            direction = "unchanged"
        
        return round(change_percent, 1), direction
    
    def check_for_changes(self, competitor_id: int) -> Optional[PriceChange]:
        """
        Check if a competitor's price has changed.
        
        Args:
            competitor_id: Database ID of competitor
            
        Returns:
            PriceChange if detected, None otherwise
        """
        if not self.db:
            return None
        
        from main import Competitor, ChangeLog
        
        competitor = self.db.query(Competitor).filter(
            Competitor.id == competitor_id
        ).first()
        
        if not competitor:
            return None
        
        # Get most recent price change from changelog
        last_price_change = self.db.query(ChangeLog).filter(
            ChangeLog.competitor_id == competitor_id,
            ChangeLog.change_type.ilike("%price%")
        ).order_by(ChangeLog.detected_at.desc()).first()
        
        if not last_price_change:
            return None
        
        # Calculate change
        change_percent, direction = self.calculate_change(
            last_price_change.previous_value,
            last_price_change.new_value
        )
        
        # Determine severity
        if change_percent is not None:
            if abs(change_percent) >= 20:
                severity = "High"
            elif abs(change_percent) >= 10:
                severity = "Medium"
            else:
                severity = "Low"
        else:
            severity = "Medium"
        
        return PriceChange(
            competitor_id=competitor_id,
            competitor_name=competitor.name,
            previous_price=last_price_change.previous_value or "Unknown",
            new_price=last_price_change.new_value or "Unknown",
            previous_numeric=self.parse_price(last_price_change.previous_value),
            new_numeric=self.parse_price(last_price_change.new_value),
            change_percent=change_percent,
            change_direction=direction,
            detected_at=last_price_change.detected_at.isoformat() if last_price_change.detected_at else datetime.utcnow().isoformat(),
            severity=severity
        )
    
    def get_price_history(self, competitor_id: int, days: int = 90) -> List[Dict[str, Any]]:
        """
        Get price history for a competitor.
        
        Args:
            competitor_id: Database ID
            days: Number of days to look back
            
        Returns:
            List of price records
        """
        if not self.db:
            return []
        
        from main import ChangeLog
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        changes = self.db.query(ChangeLog).filter(
            ChangeLog.competitor_id == competitor_id,
            ChangeLog.change_type.ilike("%price%"),
            ChangeLog.detected_at >= cutoff
        ).order_by(ChangeLog.detected_at.asc()).all()
        
        history = []
        for change in changes:
            history.append({
                "date": change.detected_at.isoformat() if change.detected_at else None,
                "previous": change.previous_value,
                "new": change.new_value,
                "previous_numeric": self.parse_price(change.previous_value),
                "new_numeric": self.parse_price(change.new_value)
            })
        
        return history
    
    def detect_price_alerts(self, threshold_percent: float = 10.0) -> List[PriceChange]:
        """
        Scan all competitors for significant price changes.
        
        Args:
            threshold_percent: Minimum change to alert on
            
        Returns:
            List of PriceChange alerts
        """
        if not self.db:
            return []
        
        from main import Competitor, ChangeLog
        
        # Get recent price changes (last 7 days)
        cutoff = datetime.utcnow() - timedelta(days=7)
        
        recent_changes = self.db.query(ChangeLog).filter(
            ChangeLog.change_type.ilike("%price%"),
            ChangeLog.detected_at >= cutoff
        ).all()
        
        alerts = []
        
        for change in recent_changes:
            change_percent, direction = self.calculate_change(
                change.previous_value,
                change.new_value
            )
            
            if change_percent is not None and abs(change_percent) >= threshold_percent:
                competitor = self.db.query(Competitor).filter(
                    Competitor.id == change.competitor_id
                ).first()
                
                if competitor:
                    alerts.append(PriceChange(
                        competitor_id=change.competitor_id,
                        competitor_name=competitor.name,
                        previous_price=change.previous_value or "Unknown",
                        new_price=change.new_value or "Unknown",
                        previous_numeric=self.parse_price(change.previous_value),
                        new_numeric=self.parse_price(change.new_value),
                        change_percent=change_percent,
                        change_direction=direction,
                        detected_at=change.detected_at.isoformat() if change.detected_at else datetime.utcnow().isoformat(),
                        severity="High" if abs(change_percent) >= 20 else "Medium"
                    ))
        
        return alerts
    
    def get_pricing_comparison(self) -> Dict[str, Any]:
        """
        Get pricing comparison across all competitors.
        
        Returns:
            Dict with pricing statistics and comparison
        """
        if not self.db:
            return {"error": "No database connection"}
        
        from main import Competitor
        
        competitors = self.db.query(Competitor).filter(
            Competitor.is_deleted == False
        ).all()
        
        pricing_data = []
        
        for comp in competitors:
            numeric = self.parse_price(comp.base_price)
            if numeric is not None:
                pricing_data.append({
                    "name": comp.name,
                    "price_display": comp.base_price,
                    "price_numeric": numeric,
                    "pricing_model": comp.pricing_model,
                    "threat_level": comp.threat_level
                })
        
        if not pricing_data:
            return {"message": "No numeric pricing data available"}
        
        # Calculate statistics
        prices = [p["price_numeric"] for p in pricing_data]
        
        return {
            "count": len(pricing_data),
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(prices),
            "median_price": sorted(prices)[len(prices) // 2],
            "competitors": sorted(pricing_data, key=lambda x: x["price_numeric"])
        }


# API convenience function
def get_price_alerts(db_session, threshold: float = 10.0) -> List[Dict[str, Any]]:
    """Get price change alerts."""
    tracker = PriceTracker(db_session)
    alerts = tracker.detect_price_alerts(threshold)
    
    return [
        {
            "competitor_id": a.competitor_id,
            "competitor_name": a.competitor_name,
            "previous_price": a.previous_price,
            "new_price": a.new_price,
            "change_percent": a.change_percent,
            "direction": a.change_direction,
            "severity": a.severity,
            "detected_at": a.detected_at
        }
        for a in alerts
    ]


if __name__ == "__main__":
    # Test price parsing
    tracker = PriceTracker()
    
    test_prices = [
        ("$99/month", "$119/month"),
        ("$5,000/year", "$6,000/year"),
        ("Contact Sales", "$199/month"),
        ("$50/user/month", "$75/user/month"),
    ]
    
    print("Price Change Analysis:")
    print("-" * 50)
    
    for old, new in test_prices:
        old_val = tracker.parse_price(old)
        new_val = tracker.parse_price(new)
        change, direction = tracker.calculate_change(old, new)
        
        print(f"{old} -> {new}")
        print(f"  Parsed: ${old_val} -> ${new_val}")
        print(f"  Change: {change}% ({direction})")
        print()
