"""
Certify Intel - Win/Loss Tracker (v5.0.7)
Tracks competitive deals and outcomes with dimension correlation.

v5.0.7: Added dimension factor tracking for Sales & Marketing module integration.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship


@dataclass
class WinLossStats:
    """Win/Loss statistics."""
    total_deals: int
    wins: int
    losses: int
    win_rate: float
    total_value_won: float
    total_value_lost: float
    by_competitor: Dict[str, Dict[str, Any]]
    loss_reasons: Dict[str, int]
    monthly_trend: List[Dict[str, Any]]
    dimension_impact: Optional[Dict[str, Dict[str, Any]]] = None  # v5.0.7


@dataclass
class DimensionCorrelation:
    """v5.0.7: Dimension impact on deal outcomes."""
    dimension_id: str
    dimension_name: str
    total_deals: int
    wins_when_strong: int  # Wins when we had advantage in this dimension
    wins_when_weak: int  # Wins when competitor had advantage
    losses_when_strong: int
    losses_when_weak: int
    win_rate_when_strong: float
    win_rate_when_weak: float
    impact_score: float  # How much this dimension impacts outcomes (-1 to 1)


class WinLossTracker:
    """Tracks competitive deal outcomes."""
    
    def __init__(self, db_session=None):
        self.db = db_session
        self._deals = []  # In-memory storage fallback
    
    def log_deal(self,
                 competitor_id: int,
                 competitor_name: str,
                 deal_name: str,
                 deal_value: Optional[float],
                 outcome: str,
                 loss_reason: Optional[str] = None,
                 notes: Optional[str] = None,
                 dimension_factors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Log a competitive deal outcome.

        Args:
            competitor_id: ID of the competitor
            competitor_name: Name of the competitor
            deal_name: Name of the deal/opportunity
            deal_value: Value in dollars
            outcome: "Won" or "Lost"
            loss_reason: Reason for loss (if applicable)
            notes: Additional notes
            dimension_factors: v5.0.7 - Dict mapping dimension_id to "advantage" or "disadvantage"
                               e.g., {"pricing_flexibility": "advantage", "integration_depth": "disadvantage"}

        Returns:
            Dict with logged deal info
        """
        deal = {
            "id": len(self._deals) + 1,
            "competitor_id": competitor_id,
            "competitor_name": competitor_name,
            "deal_name": deal_name,
            "deal_value": deal_value or 0,
            "outcome": outcome,
            "loss_reason": loss_reason,
            "notes": notes,
            "dimension_factors": dimension_factors or {},  # v5.0.7
            "logged_at": datetime.utcnow().isoformat()
        }
        
        self._deals.append(deal)
        
        # If we have a database, persist
        if self.db:
            try:
                from main import ChangeLog
                
                change = ChangeLog(
                    competitor_id=competitor_id,
                    competitor_name=competitor_name,
                    change_type=f"Deal {outcome}",
                    new_value=f"{deal_name} (${deal_value:,.0f})" if deal_value else deal_name,
                    previous_value=loss_reason if outcome == "Lost" else None,
                    source="Win/Loss Tracker",
                    severity="High" if outcome == "Lost" and deal_value and deal_value > 100000 else "Medium"
                )
                self.db.add(change)
                self.db.commit()
            except Exception as e:
                print(f"Error persisting deal: {e}")
        
        return deal
    
    def get_stats(self, days: int = 365) -> WinLossStats:
        """
        Get win/loss statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            WinLossStats with comprehensive analysis
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Filter deals by date
        recent_deals = [
            d for d in self._deals 
            if datetime.fromisoformat(d["logged_at"]) >= cutoff
        ]
        
        wins = [d for d in recent_deals if d["outcome"] == "Won"]
        losses = [d for d in recent_deals if d["outcome"] == "Lost"]
        
        total_deals = len(recent_deals)
        win_rate = (len(wins) / total_deals * 100) if total_deals > 0 else 0
        
        # Calculate values
        total_won = sum(d.get("deal_value", 0) for d in wins)
        total_lost = sum(d.get("deal_value", 0) for d in losses)
        
        # By competitor breakdown
        by_competitor = {}
        for deal in recent_deals:
            comp_name = deal["competitor_name"]
            if comp_name not in by_competitor:
                by_competitor[comp_name] = {"wins": 0, "losses": 0, "value_won": 0, "value_lost": 0}
            
            if deal["outcome"] == "Won":
                by_competitor[comp_name]["wins"] += 1
                by_competitor[comp_name]["value_won"] += deal.get("deal_value", 0)
            else:
                by_competitor[comp_name]["losses"] += 1
                by_competitor[comp_name]["value_lost"] += deal.get("deal_value", 0)
        
        # Loss reasons
        loss_reasons = {}
        for deal in losses:
            reason = deal.get("loss_reason") or "Unknown"
            loss_reasons[reason] = loss_reasons.get(reason, 0) + 1
        
        # Monthly trend (last 6 months)
        monthly_trend = self._calculate_monthly_trend(recent_deals)

        # v5.0.7: Calculate dimension impact
        dimension_impact = self._calculate_dimension_impact(recent_deals)

        return WinLossStats(
            total_deals=total_deals,
            wins=len(wins),
            losses=len(losses),
            win_rate=round(win_rate, 1),
            total_value_won=total_won,
            total_value_lost=total_lost,
            by_competitor=by_competitor,
            loss_reasons=loss_reasons,
            monthly_trend=monthly_trend,
            dimension_impact=dimension_impact
        )
    
    def _calculate_monthly_trend(self, deals: List[Dict]) -> List[Dict[str, Any]]:
        """Calculate monthly win/loss trend."""
        months = {}

        for deal in deals:
            date = datetime.fromisoformat(deal["logged_at"])
            month_key = date.strftime("%Y-%m")

            if month_key not in months:
                months[month_key] = {"month": month_key, "wins": 0, "losses": 0}

            if deal["outcome"] == "Won":
                months[month_key]["wins"] += 1
            else:
                months[month_key]["losses"] += 1

        # Sort by month
        return sorted(months.values(), key=lambda x: x["month"])[-6:]

    def _calculate_dimension_impact(self, deals: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """
        v5.0.7: Calculate how each dimension impacts win/loss outcomes.

        Args:
            deals: List of deal dicts with dimension_factors

        Returns:
            Dict mapping dimension_id to impact statistics
        """
        # Dimension names mapping
        dimension_names = {
            "product_packaging": "Product Modules & Packaging",
            "integration_depth": "Interoperability & Integration",
            "support_service": "Customer Support & Service",
            "retention_stickiness": "Retention & Stickiness",
            "user_adoption": "User Adoption & Ease of Use",
            "implementation_ttv": "Implementation & Time to Value",
            "reliability_enterprise": "Reliability & Enterprise Readiness",
            "pricing_flexibility": "Pricing & Commercial Flexibility",
            "reporting_analytics": "Reporting & Analytics"
        }

        # Initialize tracking for each dimension
        dimension_stats = {}

        for deal in deals:
            factors = deal.get("dimension_factors", {})
            if not factors:
                continue

            outcome = deal["outcome"]

            for dim_id, factor in factors.items():
                if dim_id not in dimension_stats:
                    dimension_stats[dim_id] = {
                        "dimension_id": dim_id,
                        "dimension_name": dimension_names.get(dim_id, dim_id),
                        "total_deals": 0,
                        "wins_when_advantage": 0,
                        "wins_when_disadvantage": 0,
                        "losses_when_advantage": 0,
                        "losses_when_disadvantage": 0
                    }

                stats = dimension_stats[dim_id]
                stats["total_deals"] += 1

                is_advantage = factor == "advantage"
                is_win = outcome == "Won"

                if is_advantage and is_win:
                    stats["wins_when_advantage"] += 1
                elif is_advantage and not is_win:
                    stats["losses_when_advantage"] += 1
                elif not is_advantage and is_win:
                    stats["wins_when_disadvantage"] += 1
                else:
                    stats["losses_when_disadvantage"] += 1

        # Calculate derived metrics
        for dim_id, stats in dimension_stats.items():
            total_advantage = stats["wins_when_advantage"] + stats["losses_when_advantage"]
            total_disadvantage = stats["wins_when_disadvantage"] + stats["losses_when_disadvantage"]

            # Win rates
            stats["win_rate_when_advantage"] = round(
                (stats["wins_when_advantage"] / total_advantage * 100) if total_advantage > 0 else 0, 1
            )
            stats["win_rate_when_disadvantage"] = round(
                (stats["wins_when_disadvantage"] / total_disadvantage * 100) if total_disadvantage > 0 else 0, 1
            )

            # Impact score: how much having advantage in this dimension helps (-1 to 1)
            # Positive = having advantage helps, Negative = having advantage doesn't matter
            if total_advantage > 0 and total_disadvantage > 0:
                impact = (stats["win_rate_when_advantage"] - stats["win_rate_when_disadvantage"]) / 100
            elif total_advantage > 0:
                impact = stats["win_rate_when_advantage"] / 100
            else:
                impact = 0
            stats["impact_score"] = round(impact, 2)

        return dimension_stats

    def get_dimension_correlations(self) -> List[DimensionCorrelation]:
        """
        v5.0.7: Get dimension correlations sorted by impact score.

        Returns:
            List of DimensionCorrelation objects sorted by impact (descending)
        """
        dimension_stats = self._calculate_dimension_impact(self._deals)

        correlations = []
        for dim_id, stats in dimension_stats.items():
            correlations.append(DimensionCorrelation(
                dimension_id=stats["dimension_id"],
                dimension_name=stats["dimension_name"],
                total_deals=stats["total_deals"],
                wins_when_strong=stats["wins_when_advantage"],
                wins_when_weak=stats["wins_when_disadvantage"],
                losses_when_strong=stats["losses_when_advantage"],
                losses_when_weak=stats["losses_when_disadvantage"],
                win_rate_when_strong=stats["win_rate_when_advantage"],
                win_rate_when_weak=stats["win_rate_when_disadvantage"],
                impact_score=stats["impact_score"]
            ))

        # Sort by absolute impact score (most impactful dimensions first)
        return sorted(correlations, key=lambda x: abs(x.impact_score), reverse=True)
    
    def get_competitor_performance(self, competitor_id: int) -> Dict[str, Any]:
        """
        Get win/loss performance against a specific competitor.
        
        Args:
            competitor_id: Competitor ID
            
        Returns:
            Dict with performance data
        """
        deals = [d for d in self._deals if d["competitor_id"] == competitor_id]
        
        if not deals:
            return {"message": "No deals recorded against this competitor"}
        
        wins = [d for d in deals if d["outcome"] == "Won"]
        losses = [d for d in deals if d["outcome"] == "Lost"]
        
        return {
            "competitor_id": competitor_id,
            "competitor_name": deals[0]["competitor_name"] if deals else "",
            "total_deals": len(deals),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(deals) * 100, 1) if deals else 0,
            "value_won": sum(d.get("deal_value", 0) for d in wins),
            "value_lost": sum(d.get("deal_value", 0) for d in losses),
            "loss_reasons": self._get_loss_reasons(losses),
            "recent_deals": sorted(deals, key=lambda x: x["logged_at"], reverse=True)[:5]
        }
    
    def _get_loss_reasons(self, losses: List[Dict]) -> Dict[str, int]:
        """Count loss reasons."""
        reasons = {}
        for deal in losses:
            reason = deal.get("loss_reason") or "Unknown"
            reasons[reason] = reasons.get(reason, 0) + 1
        return reasons
    
    def get_most_competitive(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get competitors we face most often.
        
        Args:
            limit: Number of competitors to return
            
        Returns:
            List of competitors sorted by deal count
        """
        competitor_counts = {}
        
        for deal in self._deals:
            comp_name = deal["competitor_name"]
            if comp_name not in competitor_counts:
                competitor_counts[comp_name] = {
                    "name": comp_name,
                    "competitor_id": deal["competitor_id"],
                    "deals": 0,
                    "wins": 0,
                    "losses": 0
                }
            
            competitor_counts[comp_name]["deals"] += 1
            if deal["outcome"] == "Won":
                competitor_counts[comp_name]["wins"] += 1
            else:
                competitor_counts[comp_name]["losses"] += 1
        
        # Sort by total deals
        sorted_comps = sorted(competitor_counts.values(), key=lambda x: x["deals"], reverse=True)
        
        # Calculate win rates
        for comp in sorted_comps:
            comp["win_rate"] = round(comp["wins"] / comp["deals"] * 100, 1) if comp["deals"] > 0 else 0
        
        return sorted_comps[:limit]


# Singleton instance for in-memory storage
_tracker_instance = None

def get_tracker(db_session=None) -> WinLossTracker:
    """Get the win/loss tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = WinLossTracker(db_session)
    elif db_session:
        _tracker_instance.db = db_session
    return _tracker_instance


# API convenience functions
def log_competitive_deal(
    competitor_id: int,
    competitor_name: str,
    deal_name: str,
    deal_value: float,
    outcome: str,
    loss_reason: str = None,
    notes: str = None,
    dimension_factors: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    Log a competitive deal.

    Args:
        competitor_id: ID of the competitor
        competitor_name: Name of the competitor
        deal_name: Name/identifier for the deal
        deal_value: Dollar value of the deal
        outcome: "Won" or "Lost"
        loss_reason: Why we lost (if applicable)
        notes: Additional notes
        dimension_factors: v5.0.7 - Dict of dimension_id -> "advantage" or "disadvantage"

    Returns:
        Dict with logged deal info
    """
    tracker = get_tracker()
    return tracker.log_deal(
        competitor_id=competitor_id,
        competitor_name=competitor_name,
        deal_name=deal_name,
        deal_value=deal_value,
        outcome=outcome,
        loss_reason=loss_reason,
        notes=notes,
        dimension_factors=dimension_factors
    )


def get_dimension_correlations() -> List[Dict[str, Any]]:
    """
    v5.0.7: Get dimension impact correlations.

    Returns:
        List of dimension correlation dicts sorted by impact
    """
    tracker = get_tracker()
    correlations = tracker.get_dimension_correlations()
    return [asdict(c) for c in correlations]


def get_win_loss_stats(days: int = 365) -> Dict[str, Any]:
    """Get win/loss statistics."""
    tracker = get_tracker()
    stats = tracker.get_stats(days)
    return asdict(stats)


if __name__ == "__main__":
    # Test the tracker
    tracker = WinLossTracker()
    
    # Log some test deals
    tracker.log_deal(1, "Phreesia", "Mercy Health System", 250000, "Won")
    tracker.log_deal(1, "Phreesia", "Cleveland Clinic", 500000, "Lost", "Price")
    tracker.log_deal(2, "Clearwave", "Baptist Health", 150000, "Won")
    tracker.log_deal(3, "athenahealth", "Penn Medicine", 750000, "Lost", "Features")
    tracker.log_deal(1, "Phreesia", "Duke Health", 300000, "Won")
    
    # Get stats
    stats = tracker.get_stats()
    print(f"Total Deals: {stats.total_deals}")
    print(f"Win Rate: {stats.win_rate}%")
    print(f"Value Won: ${stats.total_value_won:,.0f}")
    print(f"Value Lost: ${stats.total_value_lost:,.0f}")
    print(f"\nBy Competitor: {stats.by_competitor}")
    print(f"\nLoss Reasons: {stats.loss_reasons}")
