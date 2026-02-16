"""
Certify Intel v7.0 - Records Agent
===================================

Agent specialized for change tracking, audit logs, and historical data.

Features:
- View change history for competitors
- Track field-level changes with before/after
- Activity log queries
- Audit trail generation
- Historical trend analysis

All data changes are tracked with timestamps and citations.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .base_agent import BaseAgent, AgentResponse, Citation

logger = logging.getLogger(__name__)


class RecordsAgent(BaseAgent):
    """
    Agent for change tracking and audit logs.

    Capabilities:
    - View competitor change history
    - Track field-level modifications
    - Query activity logs
    - Generate audit reports
    - Analyze change trends
    """

    def __init__(self, knowledge_base=None, vector_store=None, ai_router=None):
        super().__init__(
            agent_type="records",
            ai_router=ai_router,
            vector_store=vector_store
        )
        self.knowledge_base = knowledge_base
        self.vector_store = vector_store
        self.ai_router = ai_router

    async def _get_knowledge_base_context(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve relevant documents from the knowledge base using RAG.

        Returns:
            Dict with context, citations, and metadata
        """
        if self.knowledge_base:
            try:
                filter_metadata = context.get("filter_metadata")
                result = await self.knowledge_base.get_context_for_query(
                    query=query,
                    max_chunks=5,
                    max_tokens=3000,
                    filter_metadata=filter_metadata
                )
                for cit in result.get("citations", []):
                    cit["source_type"] = "knowledge_base"
                return result
            except Exception as e:
                logger.warning(f"KB context retrieval failed: {e}")

        if self.vector_store:
            try:
                chunks = await self.vector_store.search(query, limit=5)
                context_text = "\n\n".join(c.get("content", "") for c in chunks)
                return {
                    "context": context_text,
                    "citations": [
                        {
                            "source_id": c.get("id", ""),
                            "source_type": "vector_store",
                            "content": c.get("content", "")[:200]
                        }
                        for c in chunks
                    ],
                    "chunks_found": len(chunks)
                }
            except Exception as e:
                logger.warning(f"Vector store search failed: {e}")

        return {"context": "", "citations": [], "chunks_found": 0}

    async def process(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process a records/audit query.

        Supported queries:
        - "Show change history for [competitor]"
        - "What changed this week?"
        - "Who modified [field]?"
        - "Activity log for today"
        - "Audit trail report"

        Args:
            query: Natural language records query
            context: Optional context with parameters:
                - competitor_id: For competitor-specific history
                - days: Time range (default 7)
                - change_type: Filter by type
                - user_id: Filter by user

        Returns:
            AgentResponse with records and citations
        """
        start_time = datetime.utcnow()
        context = context or {}

        try:
            query_lower = query.lower()

            # Determine action
            if any(w in query_lower for w in ["activity", "log", "user"]):
                return await self._get_activity_log(context, start_time)
            elif any(w in query_lower for w in ["audit", "trail", "report"]):
                return await self._generate_audit_report(context, start_time)
            elif context.get("competitor_id") or "competitor" in query_lower:
                return await self._get_competitor_history(context, start_time)
            else:
                return await self._get_recent_changes(context, start_time)

        except Exception as e:
            logger.error(f"Records agent error: {e}")
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text=f"I encountered an error accessing records: {str(e)}",
                citations=[],
                agent_type=self.agent_type,
                data={"error": str(e)},
                latency_ms=latency
            )

    async def _get_competitor_history(
        self,
        context: Dict[str, Any],
        start_time: datetime
    ) -> AgentResponse:
        """Get change history for a specific competitor."""
        citations = []
        competitor_id = context.get("competitor_id")
        days = context.get("days", 30)

        db = None
        try:
            from database import SessionLocal, Competitor, ChangeLog

            db = SessionLocal()

            # Get competitor
            if competitor_id:
                competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            else:
                competitor = db.query(Competitor).first()

            if not competitor:
                return AgentResponse(
                    text="No competitor found.",
                    citations=[],
                    agent_type=self.agent_type,
                    latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                )

            # Get changes
            cutoff = datetime.utcnow() - timedelta(days=days)
            changes = db.query(ChangeLog).filter(
                ChangeLog.competitor_id == competitor.id,
                ChangeLog.detected_at >= cutoff
            ).order_by(
                ChangeLog.detected_at.desc()
            ).limit(50).all()

            parts = []
            parts.append(f"## Change History: {competitor.name}\n")
            parts.append(f"*Last {days} days*\n")

            if not changes:
                parts.append("No changes recorded for this period.")
            else:
                parts.append(f"**{len(changes)} changes found:**\n")

                # Group by date
                by_date = {}
                for change in changes:
                    date_str = change.detected_at.strftime("%Y-%m-%d") if change.detected_at else "Unknown"
                    if date_str not in by_date:
                        by_date[date_str] = []
                    by_date[date_str].append(change)

                for date_str, date_changes in sorted(by_date.items(), reverse=True):
                    parts.append(f"### {date_str}")

                    for change in date_changes:
                        severity_icon = {
                            "High": "🔴",
                            "Medium": "🟡",
                            "Low": "🟢"
                        }.get(change.severity, "⚪")

                        parts.append(f"- {severity_icon} **{change.change_type}**")

                        # Show before/after if available
                        if change.previous_value or change.new_value:
                            pv = change.previous_value
                            nv = change.new_value
                            prev = pv[:50] + "..." if pv and len(pv) > 50 else pv
                            new = nv[:50] + "..." if nv and len(nv) > 50 else nv
                            parts.append(f"  - Before: `{prev or 'N/A'}`")
                            parts.append(f"  - After: `{new or 'N/A'}`")

                        if change.source:
                            parts.append(f"  - Source: {change.source}")

                        citations.append(Citation(
                            source_id=f"change_{change.id}",
                            source_type="change_log",
                            content=f"{change.change_type} on {date_str}",
                            confidence=1.0
                        ))

                    parts.append("")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "competitor_id": competitor.id,
                    "competitor_name": competitor.name,
                    "changes_count": len(changes),
                    "days": days
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error getting competitor history: {e}")
            raise
        finally:
            if db:
                db.close()

    async def _get_recent_changes(
        self,
        context: Dict[str, Any],
        start_time: datetime
    ) -> AgentResponse:
        """Get all recent changes across competitors."""
        citations = []
        days = context.get("days", 7)

        db = None
        try:
            from database import SessionLocal, ChangeLog

            db = SessionLocal()

            cutoff = datetime.utcnow() - timedelta(days=days)
            changes = db.query(ChangeLog).filter(
                ChangeLog.detected_at >= cutoff
            ).order_by(
                ChangeLog.detected_at.desc()
            ).limit(100).all()

            parts = []
            parts.append("## Recent Changes\n")
            parts.append(f"*Last {days} days*\n")

            if not changes:
                parts.append("No changes recorded for this period.")
            else:
                # Summary
                high_severity = len([c for c in changes if c.severity == "High"])
                med_severity = len([c for c in changes if c.severity == "Medium"])

                parts.append("### Summary")
                parts.append(f"- **Total Changes**: {len(changes)}")
                parts.append(f"- 🔴 High Severity: {high_severity}")
                parts.append(f"- 🟡 Medium Severity: {med_severity}")
                parts.append("")

                # Group by competitor
                by_competitor = {}
                for change in changes:
                    comp_name = change.competitor_name or "Unknown"
                    if comp_name not in by_competitor:
                        by_competitor[comp_name] = []
                    by_competitor[comp_name].append(change)

                parts.append("### Changes by Competitor")

                for comp_name, comp_changes in sorted(
                    by_competitor.items(),
                    key=lambda x: -len(x[1])
                )[:10]:
                    parts.append(f"\n**{comp_name}** ({len(comp_changes)} changes)")

                    for change in comp_changes[:3]:
                        severity_icon = {
                            "High": "🔴",
                            "Medium": "🟡",
                            "Low": "🟢"
                        }.get(change.severity, "⚪")

                        time_str = change.detected_at.strftime("%m/%d %H:%M") if change.detected_at else ""
                        parts.append(f"- {severity_icon} {change.change_type} ({time_str})")

                        citations.append(Citation(
                            source_id=f"change_{change.id}",
                            source_type="change_log",
                            content=f"{comp_name}: {change.change_type}",
                            confidence=1.0
                        ))

                    if len(comp_changes) > 3:
                        parts.append(f"  _...and {len(comp_changes) - 3} more_")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "total_changes": len(changes),
                    "days": days,
                    "high_severity": high_severity if changes else 0
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error getting recent changes: {e}")
            raise
        finally:
            if db:
                db.close()

    async def _get_activity_log(
        self,
        context: Dict[str, Any],
        start_time: datetime
    ) -> AgentResponse:
        """Get user activity log."""
        citations = []
        days = context.get("days", 1)
        user_id = context.get("user_id")

        db = None
        try:
            from database import SessionLocal, ActivityLog

            db = SessionLocal()

            cutoff = datetime.utcnow() - timedelta(days=days)
            query = db.query(ActivityLog).filter(
                ActivityLog.created_at >= cutoff
            )

            if user_id:
                query = query.filter(ActivityLog.user_id == user_id)

            activities = query.order_by(
                ActivityLog.created_at.desc()
            ).limit(50).all()

            parts = []
            parts.append("## Activity Log\n")
            parts.append(f"*Last {days} day(s)*\n")

            if not activities:
                parts.append("No activities recorded for this period.")
            else:
                parts.append(f"**{len(activities)} activities:**\n")

                # Group by action type
                by_type = {}
                for activity in activities:
                    action = activity.action_type or "unknown"
                    if action not in by_type:
                        by_type[action] = 0
                    by_type[action] += 1

                parts.append("### By Type")
                for action, count in sorted(by_type.items(), key=lambda x: -x[1]):
                    parts.append(f"- **{action}**: {count}")
                parts.append("")

                parts.append("### Recent Activity")
                for activity in activities[:15]:
                    time_str = activity.created_at.strftime("%H:%M") if activity.created_at else ""
                    user = activity.user_email or "System"
                    action = activity.action_type or "unknown"

                    parts.append(f"- [{time_str}] **{user}**: {action}")

                    # Parse details if JSON
                    if activity.action_details:
                        try:
                            details = json.loads(activity.action_details)
                            if isinstance(details, dict):
                                for k, v in list(details.items())[:2]:
                                    parts.append(f"  - {k}: {str(v)[:30]}")
                        except json.JSONDecodeError:
                            pass

                    citations.append(Citation(
                        source_id=f"activity_{activity.id}",
                        source_type="activity_log",
                        content=f"{user}: {action}",
                        confidence=1.0
                    ))

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "total_activities": len(activities),
                    "days": days
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error getting activity log: {e}")
            raise
        finally:
            if db:
                db.close()

    async def _generate_audit_report(
        self,
        context: Dict[str, Any],
        start_time: datetime
    ) -> AgentResponse:
        """Generate comprehensive audit report."""
        citations = []
        days = context.get("days", 30)

        db = None
        try:
            from database import SessionLocal, ChangeLog, ActivityLog

            db = SessionLocal()

            cutoff = datetime.utcnow() - timedelta(days=days)

            # Get stats
            total_changes = db.query(ChangeLog).filter(
                ChangeLog.detected_at >= cutoff
            ).count()

            high_severity = db.query(ChangeLog).filter(
                ChangeLog.detected_at >= cutoff,
                ChangeLog.severity == "High"
            ).count()

            total_activities = db.query(ActivityLog).filter(
                ActivityLog.created_at >= cutoff
            ).count()

            # Most active competitors
            from sqlalchemy import func
            top_changed = db.query(
                ChangeLog.competitor_name,
                func.count(ChangeLog.id).label('count')
            ).filter(
                ChangeLog.detected_at >= cutoff
            ).group_by(
                ChangeLog.competitor_name
            ).order_by(
                func.count(ChangeLog.id).desc()
            ).limit(5).all()

            parts = []
            parts.append("## Audit Report\n")
            parts.append(f"*Period: Last {days} days*\n")

            parts.append("### Summary")
            parts.append(f"- **Total Data Changes**: {total_changes}")
            parts.append(f"- **High Severity Changes**: {high_severity}")
            parts.append(f"- **User Activities**: {total_activities}")
            parts.append("")

            if top_changed:
                parts.append("### Most Changed Competitors")
                for comp_name, count in top_changed:
                    parts.append(f"- **{comp_name or 'Unknown'}**: {count} changes")
                    citations.append(Citation(
                        source_id=f"audit_{comp_name}",
                        source_type="audit",
                        content=f"{comp_name}: {count} changes",
                        confidence=1.0
                    ))
                parts.append("")

            # Health indicators
            parts.append("### Data Health")
            if high_severity > total_changes * 0.2:
                parts.append("- ⚠️ High proportion of significant changes detected")
            else:
                parts.append("- ✅ Change severity distribution normal")

            if total_activities > 0:
                parts.append(f"- ✅ Active monitoring ({total_activities} actions)")
            else:
                parts.append("- ⚠️ No user activity detected")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "total_changes": total_changes,
                    "high_severity": high_severity,
                    "total_activities": total_activities,
                    "days": days,
                    "top_changed": [{"name": n, "count": c} for n, c in top_changed] if top_changed else []
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error generating audit report: {e}")
            raise
        finally:
            if db:
                db.close()

    # Convenience methods

    async def get_competitor_changes(
        self,
        competitor_id: int,
        days: int = 30
    ) -> AgentResponse:
        """Get changes for a specific competitor."""
        return await self.process(
            "Show change history",
            context={"competitor_id": competitor_id, "days": days}
        )

    async def get_audit_report(self, days: int = 30) -> AgentResponse:
        """Get audit report."""
        return await self.process("Audit trail report", context={"days": days})
