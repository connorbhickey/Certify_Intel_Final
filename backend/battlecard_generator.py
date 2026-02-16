"""
Certify Intel - Battlecard Generator (v5.0.7)
Dynamic battlecard generation engine for sales enablement.

Creates sales-ready competitive battlecards from dimension data with:
- Full battlecards with all sections
- Quick reference cards for fast lookups
- Objection handlers for specific scenarios
- PDF export integration with reports.py

Battlecard types:
- full: Complete battlecard with all 9 dimensions, talking points, news
- quick: 1-pager with key differentiators and killer questions
- objection_handler: Focused on handling specific objections
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import os
import logging

from sales_marketing_module import (
    DimensionID,
    DIMENSION_METADATA,
    SCORE_LABELS,
    SalesMarketingModule
)

logger = logging.getLogger(__name__)


# ============== Battlecard Templates ==============

BATTLECARD_TEMPLATES = {
    "full": {
        "name": "Full Battlecard",
        "description": "Comprehensive competitive battlecard with all sections",
        "sections": [
            "quick_facts",
            "dimension_scorecard",
            "strengths_weaknesses",
            "key_differentiators",
            "common_objections",
            "counter_positioning",
            "win_themes",
            "red_flags",
            "recent_news"
        ]
    },
    "quick": {
        "name": "Quick Reference",
        "description": "1-page summary for fast competitive lookups",
        "sections": [
            "quick_facts",
            "top_3_differentiators",
            "killer_questions",
            "one_liner"
        ]
    },
    "objection_handler": {
        "name": "Objection Handler",
        "description": "Focused guide for handling specific objections",
        "sections": [
            "common_objections",
            "counter_responses",
            "proof_points"
        ]
    }
}


@dataclass
class BattlecardSection:
    """A single section of a battlecard."""
    section_id: str
    title: str
    content: Any  # Can be string, list, or dict depending on section type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "content": self.content
        }


@dataclass
class GeneratedBattlecard:
    """A complete generated battlecard."""
    competitor_id: int
    competitor_name: str
    battlecard_type: str
    title: str
    sections: List[BattlecardSection]
    generated_at: datetime
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "competitor_id": self.competitor_id,
            "competitor_name": self.competitor_name,
            "battlecard_type": self.battlecard_type,
            "title": self.title,
            "sections": [s.to_dict() for s in self.sections],
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata
        }

    def to_markdown(self) -> str:
        """Convert battlecard to markdown format."""
        lines = [
            f"# {self.title}",
            f"*Generated: {self.generated_at.strftime('%B %d, %Y at %I:%M %p')}*",
            "",
            "---",
            ""
        ]

        for section in self.sections:
            lines.append(f"## {section.title}")
            lines.append("")

            if isinstance(section.content, str):
                lines.append(section.content)
            elif isinstance(section.content, list):
                for item in section.content:
                    if isinstance(item, dict):
                        for key, value in item.items():
                            lines.append(f"**{key}**: {value}")
                    else:
                        lines.append(f"- {item}")
            elif isinstance(section.content, dict):
                for key, value in section.content.items():
                    lines.append(f"**{key}**: {value}")

            lines.append("")

        return "\n".join(lines)


class BattlecardGenerator:
    """
    Generates dynamic battlecards that update with dimension changes.
    Integrates with existing reports.py for PDF export.
    """

    def __init__(self, db_session):
        """Initialize with database session."""
        self.db = db_session
        self.sm_module = SalesMarketingModule(db_session)
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.gemini_key = os.getenv("GOOGLE_AI_API_KEY")
        self.ai_model = os.getenv("OPENAI_MODEL", "gpt-4.1")

    def _get_ai_client(self):
        """Get AI client for content generation."""
        ai_provider = os.getenv("AI_PROVIDER", "openai")

        if ai_provider == "gemini" and self.gemini_key:
            try:
                from gemini_provider import GeminiProvider
                return GeminiProvider()
            except ImportError:
                pass

        if self.openai_key:
            try:
                from openai import OpenAI
                return OpenAI(api_key=self.openai_key)
            except ImportError:
                pass

        return None

    def get_available_templates(self) -> List[Dict[str, str]]:
        """Get list of available battlecard templates."""
        return [
            {
                "type": template_type,
                "name": template["name"],
                "description": template["description"],
                "sections": template["sections"]
            }
            for template_type, template in BATTLECARD_TEMPLATES.items()
        ]

    def generate_battlecard(
        self,
        competitor_id: int,
        battlecard_type: str = "full",
        focus_dimensions: Optional[List[str]] = None,
        deal_context: Optional[str] = None
    ) -> GeneratedBattlecard:
        """
        Generate a battlecard for a competitor.

        Args:
            competitor_id: Target competitor
            battlecard_type: full, quick, or objection_handler
            focus_dimensions: Optional list of dimension IDs to emphasize
            deal_context: Optional deal-specific context for personalization

        Returns:
            GeneratedBattlecard object
        """
        from database import Competitor

        # Get competitor
        competitor = self.db.query(Competitor).filter(
            Competitor.id == competitor_id,
            Competitor.is_deleted == False
        ).first()

        if not competitor:
            raise ValueError(f"Competitor {competitor_id} not found")

        # Get template
        template = BATTLECARD_TEMPLATES.get(battlecard_type)
        if not template:
            raise ValueError(f"Invalid battlecard type: {battlecard_type}")

        # Get dimension profile
        dim_profile = self.sm_module.get_dimension_profile(competitor_id)

        # Generate sections
        sections = []
        for section_id in template["sections"]:
            section = self._generate_section(
                section_id,
                competitor,
                dim_profile,
                focus_dimensions,
                deal_context
            )
            if section:
                sections.append(section)

        return GeneratedBattlecard(
            competitor_id=competitor_id,
            competitor_name=competitor.name,
            battlecard_type=battlecard_type,
            title=f"{competitor.name} {template['name']}",
            sections=sections,
            generated_at=datetime.utcnow(),
            metadata={
                "threat_level": competitor.threat_level,
                "focus_dimensions": focus_dimensions,
                "deal_context": deal_context,
                "dimension_count": len(dim_profile.dimensions) if dim_profile else 0
            }
        )

    def _generate_section(
        self,
        section_id: str,
        competitor,
        dim_profile,
        focus_dimensions: Optional[List[str]],
        deal_context: Optional[str]
    ) -> Optional[BattlecardSection]:
        """Generate a single battlecard section."""
        generators = {
            "quick_facts": self._generate_quick_facts,
            "dimension_scorecard": self._generate_dimension_scorecard,
            "strengths_weaknesses": self._generate_strengths_weaknesses,
            "key_differentiators": self._generate_key_differentiators,
            "common_objections": self._generate_common_objections,
            "counter_positioning": self._generate_counter_positioning,
            "win_themes": self._generate_win_themes,
            "red_flags": self._generate_red_flags,
            "recent_news": self._generate_recent_news,
            "top_3_differentiators": self._generate_top_3_differentiators,
            "killer_questions": self._generate_killer_questions,
            "one_liner": self._generate_one_liner,
            "counter_responses": self._generate_counter_responses,
            "proof_points": self._generate_proof_points
        }

        generator = generators.get(section_id)
        if generator:
            return generator(competitor, dim_profile, focus_dimensions, deal_context)

        return None

    def _generate_quick_facts(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate quick facts section."""
        facts = {
            "Company": competitor.name,
            "Website": competitor.website or "N/A",
            "Threat Level": competitor.threat_level,
            "Founded": competitor.year_founded or "Unknown",
            "Headquarters": competitor.headquarters or "Unknown",
            "Employees": competitor.employee_count or "Unknown",
            "Customers": competitor.customer_count or "Unknown",
            "Pricing Model": competitor.pricing_model or "Unknown",
            "Base Price": competitor.base_price or "Contact Sales"
        }

        if competitor.is_public:
            facts["Stock"] = f"{competitor.ticker_symbol} ({competitor.stock_exchange})"

        if dim_profile and dim_profile.overall_score:
            facts["Overall Dimension Score"] = f"{dim_profile.overall_score:.1f}/5"

        return BattlecardSection(
            section_id="quick_facts",
            title="Quick Facts",
            content=facts
        )

    def _generate_dimension_scorecard(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate dimension scorecard section."""
        if not dim_profile:
            return BattlecardSection(
                section_id="dimension_scorecard",
                title="Dimension Scorecard",
                content="No dimension scores available. Score this competitor to enable battlecard generation."
            )

        scorecard = []
        for dim_id in DimensionID:
            meta = DIMENSION_METADATA[dim_id]
            dim_data = dim_profile.dimensions.get(dim_id.value)

            score = dim_data.score if dim_data else None
            evidence = dim_data.evidence if dim_data else None

            scorecard.append({
                "dimension": f"{meta['icon']} {meta['short_name']}",
                "score": f"{score}/5 ({SCORE_LABELS.get(score, 'Not Scored')})" if score else "Not Scored",
                "evidence": evidence[:100] + "..." if evidence and len(evidence) > 100 else evidence or "No evidence"
            })

        return BattlecardSection(
            section_id="dimension_scorecard",
            title="9-Dimension Scorecard",
            content=scorecard
        )

    def _generate_strengths_weaknesses(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate strengths and weaknesses section."""
        content = {"strengths": [], "weaknesses": [], "neutral": []}

        if dim_profile:
            for dim_id_str, dim_score in dim_profile.dimensions.items():
                meta = DIMENSION_METADATA.get(DimensionID(dim_id_str), {})
                dim_name = meta.get("name", dim_id_str)

                if dim_score.score >= 4:
                    content["strengths"].append({
                        "dimension": dim_name,
                        "score": dim_score.score,
                        "evidence": dim_score.evidence[:150] if dim_score.evidence else "Strong performance"
                    })
                elif dim_score.score <= 2:
                    content["weaknesses"].append({
                        "dimension": dim_name,
                        "score": dim_score.score,
                        "evidence": dim_score.evidence[:150] if dim_score.evidence else "Area of concern"
                    })
                else:
                    content["neutral"].append({
                        "dimension": dim_name,
                        "score": dim_score.score
                    })

        return BattlecardSection(
            section_id="strengths_weaknesses",
            title="Strengths & Weaknesses Analysis",
            content=content
        )

    def _generate_key_differentiators(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate key differentiators vs Certify Health."""
        differentiators = []

        # Based on dimension weaknesses - these are our differentiators
        if dim_profile:
            for weakness_id in dim_profile.weaknesses:
                meta = DIMENSION_METADATA.get(DimensionID(weakness_id), {})
                dim_data = dim_profile.dimensions.get(weakness_id)

                differentiators.append({
                    "area": meta.get("name", weakness_id),
                    "their_position": f"Score: {dim_data.score}/5" if dim_data else "Weak",
                    "our_advantage": meta.get("deal_impact", "Key differentiator opportunity"),
                    "talking_point": f"While {competitor.name} struggles with {meta.get('short_name', 'this area')}, Certify Health excels here."
                })

        # Add product-based differentiators
        if not competitor.has_pxp:
            differentiators.append({
                "area": "Patient Experience Platform",
                "their_position": "Not offered",
                "our_advantage": "Complete PXP solution",
                "talking_point": f"{competitor.name} lacks a dedicated Patient Experience Platform."
            })

        if not competitor.has_biometric:
            differentiators.append({
                "area": "Biometric Authentication",
                "their_position": "Not available",
                "our_advantage": "FaceCheck biometric identity",
                "talking_point": f"{competitor.name} cannot match our biometric patient identity verification."
            })

        return BattlecardSection(
            section_id="key_differentiators",
            title="Key Differentiators (vs Certify Health)",
            content=differentiators[:5]  # Top 5
        )

    def _generate_common_objections(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate common objections section."""
        objections = []

        # Based on their strengths - prospects might raise these
        if dim_profile:
            for strength_id in dim_profile.strengths:
                meta = DIMENSION_METADATA.get(DimensionID(strength_id), {})
                dim_data = dim_profile.dimensions.get(strength_id)

                objections.append({
                    "objection": f"'{competitor.name} is stronger in {meta.get('short_name', 'this area')}'",
                    "dimension": meta.get("name"),
                    "their_claim": dim_data.evidence[:100] if dim_data and dim_data.evidence else "Strong performance claimed"
                })

        # Standard objections
        if competitor.customer_count:
            objections.append({
                "objection": f"'{competitor.name} has {competitor.customer_count} customers'",
                "dimension": "Market Presence",
                "their_claim": "Large install base"
            })

        if competitor.threat_level == "High":
            objections.append({
                "objection": f"'We're already evaluating {competitor.name}'",
                "dimension": "Competitive Position",
                "their_claim": "Industry recognized player"
            })

        return BattlecardSection(
            section_id="common_objections",
            title="Common Objections You'll Hear",
            content=objections[:5]
        )

    def _generate_counter_positioning(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate counter-positioning strategies."""
        # Use AI to generate if available
        client = self._get_ai_client()

        if client and dim_profile:
            try:
                strengths_text = ", ".join([
                    DIMENSION_METADATA.get(DimensionID(s), {}).get("name", s)
                    for s in dim_profile.strengths
                ])
                weaknesses_text = ", ".join([
                    DIMENSION_METADATA.get(DimensionID(w), {}).get("name", w)
                    for w in dim_profile.weaknesses
                ])

                prompt = f"""Generate 3 counter-positioning statements for competing against {competitor.name}.

Their Strengths: {strengths_text or "Unknown"}
Their Weaknesses: {weaknesses_text or "Unknown"}
Their Threat Level: {competitor.threat_level}

For each statement, provide:
1. The positioning angle
2. A brief talking point (1-2 sentences)

Keep responses focused on healthcare technology buyers."""

                if hasattr(client, 'generate_text'):
                    response = client.generate_text(prompt)
                    if response.success:
                        return BattlecardSection(
                            section_id="counter_positioning",
                            title="Counter-Positioning Strategies",
                            content=response.content
                        )
                else:
                    response = client.chat.completions.create(
                        model=self.ai_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.5,
                        max_tokens=500
                    )
                    return BattlecardSection(
                        section_id="counter_positioning",
                        title="Counter-Positioning Strategies",
                        content=response.choices[0].message.content
                    )
            except Exception as e:
                logger.error(f"AI counter-positioning failed: {e}")

        # Fallback to template-based
        strategies = [
            f"Focus on {competitor.name}'s dimension weaknesses during discovery",
            "Emphasize Certify Health's superior integration depth and EHR partnerships",
            "Lead with ROI and time-to-value metrics where we excel"
        ]

        return BattlecardSection(
            section_id="counter_positioning",
            title="Counter-Positioning Strategies",
            content=strategies
        )

    def _generate_win_themes(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate themes that help win against this competitor."""
        themes = []

        if dim_profile:
            # Win on their weaknesses
            for weakness_id in dim_profile.weaknesses[:3]:
                meta = DIMENSION_METADATA.get(DimensionID(weakness_id), {})
                themes.append({
                    "theme": meta.get("name", weakness_id),
                    "message": f"Highlight our strength in {meta.get('short_name', 'this area')} - they score low here",
                    "deal_impact": meta.get("deal_impact", "")
                })

        # Default themes
        themes.extend([
            {
                "theme": "Modern Platform",
                "message": "Emphasize our modern, API-first architecture",
                "deal_impact": "IT teams value future-proof solutions"
            },
            {
                "theme": "Healthcare Focus",
                "message": "We're built specifically for healthcare workflows",
                "deal_impact": "Buyers want domain expertise"
            }
        ])

        return BattlecardSection(
            section_id="win_themes",
            title="Winning Themes Against " + competitor.name,
            content=themes[:5]
        )

    def _generate_red_flags(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate red flags to watch for in deals."""
        red_flags = []

        if competitor.threat_level == "High":
            red_flags.append("High threat competitor - expect aggressive pricing and tactics")

        if dim_profile:
            for strength_id in dim_profile.strengths[:2]:
                meta = DIMENSION_METADATA.get(DimensionID(strength_id), {})
                red_flags.append(f"Strong in {meta.get('short_name', 'key areas')} - prepare counter-points")

        if competitor.customer_count:
            red_flags.append(f"Large install base ({competitor.customer_count}) - may have existing relationships")

        red_flags.extend([
            "Watch for incumbent advantage if prospect has existing vendor",
            "Budget constraints may favor their pricing model"
        ])

        return BattlecardSection(
            section_id="red_flags",
            title="Red Flags to Watch For",
            content=red_flags[:5]
        )

    def _generate_recent_news(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate recent news section."""
        from database import DimensionNewsTag

        # Get recent news tags
        cutoff = datetime.utcnow() - timedelta(days=30)
        news_tags = self.db.query(DimensionNewsTag).filter(
            DimensionNewsTag.competitor_id == competitor.id,
            DimensionNewsTag.tagged_at >= cutoff
        ).order_by(DimensionNewsTag.tagged_at.desc()).limit(5).all()

        if not news_tags:
            return BattlecardSection(
                section_id="recent_news",
                title="Recent News",
                content="No recent news tagged for this competitor."
            )

        news_items = []
        for tag in news_tags:
            meta = DIMENSION_METADATA.get(DimensionID(tag.dimension_id), {})
            news_items.append({
                "title": tag.news_title,
                "dimension": meta.get("short_name", tag.dimension_id),
                "sentiment": tag.sentiment or "neutral",
                "date": tag.tagged_at.strftime("%Y-%m-%d")
            })

        return BattlecardSection(
            section_id="recent_news",
            title="Recent News (Last 30 Days)",
            content=news_items
        )

    def _generate_top_3_differentiators(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate top 3 differentiators for quick card."""
        diffs = []

        if dim_profile and dim_profile.weaknesses:
            for weakness_id in dim_profile.weaknesses[:3]:
                meta = DIMENSION_METADATA.get(DimensionID(weakness_id), {})
                diffs.append(f"{meta.get('icon', '•')} {meta.get('name')}: We excel where they struggle")

        while len(diffs) < 3:
            diffs.append("• Ask about our unique healthcare-specific capabilities")

        return BattlecardSection(
            section_id="top_3_differentiators",
            title="Top 3 Differentiators",
            content=diffs[:3]
        )

    def _generate_killer_questions(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate killer questions to ask prospects."""
        questions = []

        if dim_profile:
            for weakness_id in dim_profile.weaknesses[:2]:
                meta = DIMENSION_METADATA.get(DimensionID(weakness_id), {})
                questions.append(f"How important is {meta.get('short_name', 'this area')} to your evaluation criteria?")

        questions.extend([
            f"Have you evaluated {competitor.name}'s pricing model for hidden costs?",
            "What's your timeline for go-live, and how critical is implementation speed?",
            "Which EHR integrations are must-haves for your workflow?"
        ])

        return BattlecardSection(
            section_id="killer_questions",
            title="Killer Questions to Ask",
            content=questions[:5]
        )

    def _generate_one_liner(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate a one-liner positioning statement."""
        if dim_profile and dim_profile.weaknesses:
            weakness_meta = DIMENSION_METADATA.get(DimensionID(dim_profile.weaknesses[0]), {})
            one_liner = f"While {competitor.name} has market presence, their {weakness_meta.get('short_name', 'key area')} challenges create opportunity for Certify Health's differentiated approach."
        else:
            one_liner = f"Certify Health offers a modern, healthcare-focused alternative to {competitor.name} with superior integration and time-to-value."

        return BattlecardSection(
            section_id="one_liner",
            title="One-Liner Positioning",
            content=one_liner
        )

    def _generate_counter_responses(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate counter-responses for objection handler."""
        responses = []

        if dim_profile:
            for strength_id in dim_profile.strengths[:3]:
                meta = DIMENSION_METADATA.get(DimensionID(strength_id), {})
                responses.append({
                    "objection": f"They're strong in {meta.get('short_name', 'this area')}",
                    "response": f"Acknowledge their {meta.get('short_name', 'strength')}, then pivot to what matters more for the prospect's specific needs",
                    "proof": "Reference customer success stories where we won despite this"
                })

        return BattlecardSection(
            section_id="counter_responses",
            title="Counter-Responses",
            content=responses
        )

    def _generate_proof_points(self, competitor, dim_profile, focus_dims, deal_context) -> BattlecardSection:
        """Generate proof points to support claims."""
        proof_points = [
            "Customer testimonials from similar-sized organizations",
            "Implementation timeline case studies showing faster TTV",
            "ROI calculator demonstrating cost savings"
        ]

        if dim_profile and dim_profile.weaknesses:
            for weakness_id in dim_profile.weaknesses[:2]:
                meta = DIMENSION_METADATA.get(DimensionID(weakness_id), {})
                proof_points.append(f"Comparative analysis showing our {meta.get('short_name', 'advantage')}")

        return BattlecardSection(
            section_id="proof_points",
            title="Proof Points to Reference",
            content=proof_points[:5]
        )

    def save_battlecard(
        self,
        battlecard: GeneratedBattlecard,
        user_email: str
    ) -> int:
        """Save a generated battlecard to the database."""
        from database import Battlecard

        db_battlecard = Battlecard(
            competitor_id=battlecard.competitor_id,
            title=battlecard.title,
            content=json.dumps(battlecard.to_dict()),
            battlecard_type=battlecard.battlecard_type,
            focus_dimensions=json.dumps(battlecard.metadata.get("focus_dimensions")),
            deal_context=battlecard.metadata.get("deal_context"),
            generated_at=battlecard.generated_at,
            generated_by=user_email,
            is_active=True,
            version=1
        )

        self.db.add(db_battlecard)
        self.db.commit()

        return db_battlecard.id

    def get_battlecard(self, battlecard_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a saved battlecard by ID."""
        from database import Battlecard

        bc = self.db.query(Battlecard).filter(
            Battlecard.id == battlecard_id,
            Battlecard.is_active == True
        ).first()

        if not bc:
            return None

        return {
            "id": bc.id,
            "competitor_id": bc.competitor_id,
            "title": bc.title,
            "content": json.loads(bc.content) if bc.content else None,
            "battlecard_type": bc.battlecard_type,
            "generated_at": bc.generated_at.isoformat(),
            "generated_by": bc.generated_by,
            "version": bc.version
        }

    def list_battlecards(self, competitor_id: int) -> List[Dict[str, Any]]:
        """List all battlecards for a competitor."""
        from database import Battlecard

        battlecards = self.db.query(Battlecard).filter(
            Battlecard.competitor_id == competitor_id,
            Battlecard.is_active == True
        ).order_by(Battlecard.generated_at.desc()).all()

        return [
            {
                "id": bc.id,
                "title": bc.title,
                "battlecard_type": bc.battlecard_type,
                "generated_at": bc.generated_at.isoformat(),
                "generated_by": bc.generated_by,
                "version": bc.version
            }
            for bc in battlecards
        ]

    def export_to_pdf(self, battlecard_id: int) -> Optional[bytes]:
        """Export battlecard to PDF using existing reports.py."""
        bc_data = self.get_battlecard(battlecard_id)
        if not bc_data:
            return None

        try:
            from reports import generate_battlecard_pdf

            # Convert to markdown first
            content = bc_data.get("content", {})
            if isinstance(content, str):
                content = json.loads(content)

            # Create a GeneratedBattlecard object for markdown conversion
            sections = [
                BattlecardSection(
                    section_id=s["section_id"],
                    title=s["title"],
                    content=s["content"]
                )
                for s in content.get("sections", [])
            ]

            battlecard = GeneratedBattlecard(
                competitor_id=content.get("competitor_id", 0),
                competitor_name=content.get("competitor_name", "Unknown"),
                battlecard_type=content.get("battlecard_type", "full"),
                title=content.get("title", "Battlecard"),
                sections=sections,
                generated_at=datetime.fromisoformat(content.get("generated_at", datetime.utcnow().isoformat())),
                metadata=content.get("metadata", {})
            )

            markdown_content = battlecard.to_markdown()

            # Use reports.py to generate PDF
            return generate_battlecard_pdf(
                competitor_name=battlecard.competitor_name,
                content=markdown_content
            )

        except ImportError:
            logger.warning("reports.py not available for PDF export")
            return None
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return None
