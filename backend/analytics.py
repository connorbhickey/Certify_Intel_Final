"""
Certify Intel - Analytics Engine
Threat scoring, market share estimation, feature gap analysis, competitive intelligence
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

# Import models
try:
    from database import SessionLocal, Competitor
except ImportError:
    pass


# ============== Threat Score Algorithm ==============

@dataclass
class ThreatScore:
    """Computed threat score for a competitor."""
    overall_score: float  # 0-100
    threat_level: str  # High, Medium, Low
    components: Dict[str, float]
    signals: List[str]
    recommendations: List[str]


class ThreatScoreCalculator:
    """Calculates threat scores based on multiple factors."""
    
    # Weight factors for different signals
    WEIGHTS = {
        "product_overlap": 0.20,         # How many of Certify's 7 products they compete with
        "market_overlap": 0.15,          # How many of Certify's 11 markets they target
        "customer_size_overlap": 0.10,   # Target similar practice sizes
        "funding_strength": 0.15,        # Financial resources
        "growth_rate": 0.15,             # How fast they're growing
        "product_breadth": 0.05,         # Feature coverage
        "customer_base": 0.10,           # Installed base size
        "pricing_competition": 0.05,     # Price positioning
        "innovation_rate": 0.05,         # New product launches
    }
    
    # Certify Health's 7 Product Categories (keywords for overlap detection)
    CERTIFY_PRODUCTS = {
        "pxp": [
            "patient experience", "appointment scheduling", "digital intake", "self-scheduling",
            "patient reminders", "nudges", "patient communication", "post-visit", 
            "patient portal", "brand experience", "check-in", "kiosk"
        ],
        "pms": [
            "practice management", "scheduling", "registration", "front office", 
            "back office", "billing ops", "reporting", "appointments", "waitlist"
        ],
        "rcm": [
            "revenue cycle", "patient payments", "claims", "billing", "collections",
            "denial management", "payment gateway", "text to pay", "autopay",
            "eligibility verification", "insurance verification", "copay"
        ],
        "patient_mgmt": [
            "patient chart", "clinical documentation", "care coordination", 
            "orders", "ai scribe", "encounter", "soap notes", "ehr", "emr",
            "patient record", "vitals", "medical history"
        ],
        "certify_pay": [
            "patient payments", "text to pay", "autopay", "merchant services",
            "payment collection", "healthcare payments", "medical payments"
        ],
        "facecheck": [
            "biometric", "facial recognition", "identity verification", 
            "patient identification", "touchless", "photo id"
        ],
        "interoperability": [
            "ehr integration", "fhir", "hl7", "epic", "cerner", "athena",
            "nextgen", "eclinicalworks", "allscripts", "api", "interoperability"
        ]
    }
    
    # Certify Health's 11 Market Verticals (keywords for overlap detection)
    CERTIFY_MARKETS = {
        "hospitals": [
            "hospital", "health system", "general hospital", "teaching hospital",
            "specialty hospital", "imaging department", "inpatient"
        ],
        "ambulatory": [
            "ambulatory", "outpatient", "urgent care", "walk-in", "asc",
            "ambulatory surgical", "imaging center", "retail clinic", "primary care"
        ],
        "long_term": [
            "nursing home", "assisted living", "snf", "skilled nursing", 
            "memory care", "palliative", "long-term care", "rehabilitation"
        ],
        "behavioral": [
            "behavioral health", "mental health", "substance abuse", "psychiatric",
            "crisis stabilization", "counseling", "therapy"
        ],
        "specialized": [
            "dialysis", "fertility", "ivf", "sleep center", "pain management", 
            "wound care", "hyperbaric"
        ],
        "telehealth": [
            "telehealth", "telemedicine", "virtual care", "remote monitoring", 
            "rpm", "digital therapeutics", "chronic disease management"
        ],
        "labs": [
            "laboratory", "diagnostic", "pathology", "genetic testing", 
            "toxicology", "lab", "blood test"
        ],
        "managed_care": [
            "hmo", "ppo", "aco", "tpa", "medicare", "medicaid", 
            "managed care", "health plan", "payer"
        ],
        "enterprise": [
            "multi-specialty", "idn", "dso", "dental service organization",
            "group practice", "multi-location", "enterprise"
        ],
        "occupational": [
            "occupational health", "corporate health", "employee health", 
            "workplace clinic", "corporate wellness"
        ],
        "government": [
            "va hospital", "veterans", "military", "public health", 
            "community health", "fqhc", "government"
        ]
    }
    
    # Legacy flat list for backwards compatibility
    CERTIFY_SEGMENTS = [
        "patient intake", "eligibility verification", "payments",
        "patient engagement", "check-in", "registration"
    ]
    
    CERTIFY_SIZE_FOCUS = ["medium", "large", "enterprise"]
    
    def calculate(self, competitor: Dict[str, Any]) -> ThreatScore:
        """Calculate threat score for a competitor."""
        components = {}
        signals = []
        recommendations = []
        
        # 1. Market Overlap Score
        segments = (competitor.get("target_segments") or "").lower()
        overlap_count = sum(1 for s in self.CERTIFY_SEGMENTS if s in segments)
        components["market_overlap"] = min(overlap_count / len(self.CERTIFY_SEGMENTS) * 100, 100)
        
        if components["market_overlap"] > 50:
            signals.append(f"High market overlap ({overlap_count} segments)")
        
        # 2. Customer Size Overlap
        size_focus = (competitor.get("customer_size_focus") or "").lower()
        size_overlap = any(s in size_focus for s in self.CERTIFY_SIZE_FOCUS)
        components["customer_size_overlap"] = 80 if size_overlap else 30
        
        # 3. Funding Strength
        funding = (competitor.get("funding_total") or "").lower()
        if "public" in funding or ">$100m" in funding or "$100m" in funding or "$300m" in funding:
            components["funding_strength"] = 90
            signals.append("Well-funded competitor")
        elif "$50m" in funding or "$40m" in funding:
            components["funding_strength"] = 60
        else:
            components["funding_strength"] = 30
        
        # 4. Growth Rate
        growth = (competitor.get("employee_growth_rate") or "").lower()
        if "20%" in growth or "25%" in growth or "30%" in growth:
            components["growth_rate"] = 90
            signals.append("Rapid growth detected")
            recommendations.append(f"Monitor {competitor.get('name')} for aggressive expansion")
        elif "10%" in growth or "15%" in growth:
            components["growth_rate"] = 60
        else:
            components["growth_rate"] = 30
        
        # 5. Product Breadth
        products = (competitor.get("product_categories") or "").lower()
        product_count = len(products.split(";")) if products else 0
        components["product_breadth"] = min(product_count * 20, 100)
        
        # 6. Customer Base
        customers = competitor.get("customer_count") or ""
        if "100000" in customers or "75000" in customers or "40000" in customers:
            components["customer_base"] = 95
            signals.append("Large installed base")
        elif "3000" in customers or "5000" in customers or "25000" in customers:
            components["customer_base"] = 70
        elif "500" in customers or "1000" in customers:
            components["customer_base"] = 50
        else:
            components["customer_base"] = 30
        
        # 7. Pricing Competition
        price = (competitor.get("base_price") or "").lower()
        pricing_model = (competitor.get("pricing_model") or "").lower()
        if "$3" in price or "per visit" in pricing_model:
            components["pricing_competition"] = 80  # Transaction-based pricing
        elif "subscription" in pricing_model or "$29" in price or "$49" in price:
            components["pricing_competition"] = 60  # Low-cost subscription
        else:
            components["pricing_competition"] = 40
        
        # 8. Innovation Rate
        launches = competitor.get("recent_launches") or ""
        if "ai" in launches.lower() or "2024" in launches or "2025" in launches:
            components["innovation_rate"] = 80
            signals.append("Recent AI/innovation launch detected")
        else:
            components["innovation_rate"] = 40
        
        # Calculate overall weighted score
        overall_score = sum(
            components.get(k, 0) * v 
            for k, v in self.WEIGHTS.items()
        )
        
        # Determine threat level
        if overall_score >= 70:
            threat_level = "High"
            recommendations.append(f"Prioritize competitive response to {competitor.get('name')}")
        elif overall_score >= 45:
            threat_level = "Medium"
            recommendations.append(f"Monitor {competitor.get('name')} quarterly")
        else:
            threat_level = "Low"
        
        return ThreatScore(
            overall_score=round(overall_score, 1),
            threat_level=threat_level,
            components=components,
            signals=signals,
            recommendations=recommendations
        )


# ============== Market Share Estimation ==============

@dataclass
class MarketShare:
    """Estimated market share data."""
    estimated_share: float  # Percentage
    confidence: str  # High, Medium, Low
    methodology: str
    data_points: Dict[str, Any]


class MarketShareEstimator:
    """Estimates market share based on available data."""
    
    # Market size estimate for patient intake/engagement
    TOTAL_MARKET_SIZE = 15000  # Estimated total addressable practices in US
    
    def estimate(self, competitor: Dict[str, Any]) -> MarketShare:
        """Estimate competitor market share."""
        data_points = {}
        
        # Extract customer count
        customer_str = competitor.get("customer_count") or "0"
        customers = self._parse_number(customer_str)
        data_points["customers"] = customers
        
        # Extract employee count for revenue estimation
        employee_str = competitor.get("employee_count") or "0"
        employees = self._parse_number(employee_str)
        data_points["employees"] = employees
        
        # Estimate based on customers
        if customers > 0:
            share = (customers / self.TOTAL_MARKET_SIZE) * 100
            confidence = "High" if "+" not in customer_str else "Medium"
            methodology = "Customer count based"
        # Fallback: estimate from employee count
        elif employees > 0:
            # Rough estimate: 1 employee per 50-100 customers
            estimated_customers = employees * 75
            share = (estimated_customers / self.TOTAL_MARKET_SIZE) * 100
            confidence = "Low"
            methodology = "Employee-based estimate"
        else:
            share = 0.5  # Default minimal share
            confidence = "Low"
            methodology = "Default estimate"
        
        # Cap at reasonable maximum
        share = min(share, 50)
        
        data_points["total_market"] = self.TOTAL_MARKET_SIZE
        
        return MarketShare(
            estimated_share=round(share, 2),
            confidence=confidence,
            methodology=methodology,
            data_points=data_points
        )
    
    def _parse_number(self, s: str) -> int:
        """Parse a number string like '3000+' or '1,500'."""
        import re
        s = s.replace(",", "").replace("+", "")
        match = re.search(r'\d+', s)
        return int(match.group()) if match else 0


# ============== Feature Gap Analysis ==============

@dataclass
class FeatureGap:
    """Feature gap analysis result."""
    category: str
    feature: str
    competitor_has: bool
    certify_has: bool
    gap_type: str  # "advantage", "disadvantage", "parity"
    priority: str  # "high", "medium", "low"


class FeatureAnalyzer:
    """Analyzes feature gaps between Certify and competitors."""
    
    # Certify Health's features (assumed)
    CERTIFY_FEATURES = {
        "patient_intake": True,
        "digital_forms": True,
        "insurance_verification": True,
        "eligibility_check": True,
        "patient_payments": True,
        "appointment_reminders": True,
        "check_in_kiosk": True,
        "hipaa_compliance": True,
        "ehr_integration": True,
        # Features Certify may not have
        "telehealth": False,
        "practice_management": False,
        "full_ehr": False,
        "rcm_billing": False,
        "patient_portal": True,
        "two_way_texting": True,
        "ai_scheduling": False,
        "population_health": False,
    }
    
    FEATURE_PRIORITY = {
        "telehealth": "high",
        "ai_scheduling": "high",
        "two_way_texting": "medium",
        "rcm_billing": "medium",
        "population_health": "low",
        "full_ehr": "low",
    }
    
    def analyze(self, competitor: Dict[str, Any]) -> List[FeatureGap]:
        """Analyze feature gaps with a competitor."""
        gaps = []
        
        features_str = (competitor.get("key_features") or "").lower()
        products_str = (competitor.get("product_categories") or "").lower()
        combined = features_str + " " + products_str
        
        # Check each feature
        feature_keywords = {
            "patient_intake": ["intake", "registration", "check-in"],
            "digital_forms": ["forms", "digital", "paperless"],
            "insurance_verification": ["eligibility", "insurance", "verification"],
            "patient_payments": ["payment", "collect", "billing"],
            "appointment_reminders": ["reminder", "notification", "alert"],
            "check_in_kiosk": ["kiosk", "self-service", "check-in"],
            "telehealth": ["telehealth", "video", "virtual"],
            "practice_management": ["practice management", "pm", "scheduling"],
            "full_ehr": ["ehr", "electronic health record", "emr"],
            "rcm_billing": ["rcm", "revenue cycle", "billing"],
            "patient_portal": ["portal", "patient access"],
            "two_way_texting": ["texting", "sms", "two-way"],
            "ai_scheduling": ["ai", "intelligent", "smart scheduling"],
            "population_health": ["population health", "analytics"],
        }
        
        for feature, keywords in feature_keywords.items():
            competitor_has = any(kw in combined for kw in keywords)
            certify_has = self.CERTIFY_FEATURES.get(feature, False)
            
            if competitor_has and not certify_has:
                gap_type = "disadvantage"
            elif certify_has and not competitor_has:
                gap_type = "advantage"
            else:
                gap_type = "parity"
            
            priority = self.FEATURE_PRIORITY.get(feature, "low")
            
            gaps.append(FeatureGap(
                category="product",
                feature=feature.replace("_", " ").title(),
                competitor_has=competitor_has,
                certify_has=certify_has,
                gap_type=gap_type,
                priority=priority
            ))
        
        return gaps
    
    def summarize_gaps(self, gaps: List[FeatureGap]) -> Dict[str, Any]:
        """Summarize feature gaps."""
        advantages = [g for g in gaps if g.gap_type == "advantage"]
        disadvantages = [g for g in gaps if g.gap_type == "disadvantage"]
        parity = [g for g in gaps if g.gap_type == "parity"]
        
        high_priority_gaps = [g for g in disadvantages if g.priority == "high"]
        
        return {
            "total_features": len(gaps),
            "advantages": len(advantages),
            "disadvantages": len(disadvantages),
            "parity": len(parity),
            "high_priority_gaps": [g.feature for g in high_priority_gaps],
            "advantage_features": [g.feature for g in advantages],
            "gap_features": [g.feature for g in disadvantages],
        }


# ============== Competitive Heatmap Data ==============

class CompetitiveHeatmap:
    """Generates heatmap data for competitive analysis."""
    
    CATEGORIES = [
        "pricing", "features", "market_presence", 
        "technology", "customer_success", "growth"
    ]
    
    def generate_heatmap_data(self, competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate heatmap matrix data."""
        heatmap = {
            "categories": self.CATEGORIES,
            "competitors": [],
            "scores": []
        }
        
        for comp in competitors:
            name = comp.get("name", "Unknown")
            heatmap["competitors"].append(name)
            
            scores = {
                "pricing": self._score_pricing(comp),
                "features": self._score_features(comp),
                "market_presence": self._score_market(comp),
                "technology": self._score_technology(comp),
                "customer_success": self._score_customer_success(comp),
                "growth": self._score_growth(comp),
            }
            
            heatmap["scores"].append({
                "competitor": name,
                "values": scores
            })
        
        return heatmap
    
    def _score_pricing(self, comp: Dict) -> int:
        """Score pricing competitiveness (1-10, 10 = most competitive/lowest)."""
        price = (comp.get("base_price") or "").lower()
        if "$3" in price or "$29" in price:
            return 9
        elif "$150" in price or "$199" in price:
            return 6
        elif "$300" in price or "$400" in price:
            return 4
        elif "custom" in price:
            return 3
        return 5
    
    def _score_features(self, comp: Dict) -> int:
        """Score feature completeness (1-10)."""
        products = comp.get("product_categories") or ""
        features = comp.get("key_features") or ""
        combined = products + " " + features
        
        count = len(combined.split(";")) + len(combined.split(","))
        return min(count, 10)
    
    def _score_market(self, comp: Dict) -> int:
        """Score market presence (1-10)."""
        customers = comp.get("customer_count") or ""
        if "100000" in customers or "75000" in customers:
            return 10
        elif "25000" in customers or "40000" in customers:
            return 8
        elif "3000" in customers or "5000" in customers:
            return 6
        elif "500" in customers or "1000" in customers:
            return 4
        return 3
    
    def _score_technology(self, comp: Dict) -> int:
        """Score technology/innovation (1-10)."""
        features = (comp.get("key_features") or "").lower()
        launches = (comp.get("recent_launches") or "").lower()
        
        score = 5
        if "ai" in features or "ai" in launches:
            score += 2
        if "mobile" in features:
            score += 1
        if "cloud" in features:
            score += 1
        return min(score, 10)
    
    def _score_customer_success(self, comp: Dict) -> int:
        """Score customer satisfaction (1-10)."""
        rating = comp.get("g2_rating") or "4.0"
        try:
            r = float(rating)
            return int(r * 2)  # Convert 1-5 to 1-10
        except:
            return 5
    
    def _score_growth(self, comp: Dict) -> int:
        """Score growth trajectory (1-10)."""
        growth = (comp.get("employee_growth_rate") or "").lower()
        if "25%" in growth or "30%" in growth:
            return 10
        elif "20%" in growth:
            return 8
        elif "15%" in growth:
            return 7
        elif "10%" in growth:
            return 5
        elif "5%" in growth:
            return 4
        return 3


# ============== AI Competitor Summary ==============

class CompetitorSummarizer:
    """Generates AI-powered competitor summaries."""
    
    def generate_summary(self, competitor: Dict[str, Any]) -> str:
        """Generate a one-paragraph summary of a competitor."""
        name = competitor.get("name", "Unknown")
        
        # Build summary from data
        parts = []
        
        # Company basics
        founded = competitor.get("year_founded")
        hq = competitor.get("headquarters")
        if founded and hq:
            parts.append(f"{name}, founded in {founded} and headquartered in {hq}")
        else:
            parts.append(f"{name}")
        
        # Products
        products = competitor.get("product_categories")
        if products:
            parts.append(f"offers {products.replace(';', ',')}")
        
        # Market position
        customers = competitor.get("customer_count")
        segments = competitor.get("target_segments")
        if customers:
            parts.append(f"serves {customers} customers")
        if segments:
            parts.append(f"primarily targeting {segments.replace(';', ' and ')}")
        
        # Pricing
        pricing = competitor.get("pricing_model")
        price = competitor.get("base_price")
        if pricing and price:
            parts.append(f"with {pricing} pricing starting at {price}")
        
        # Funding/status
        funding = competitor.get("funding_total")
        latest = competitor.get("latest_round")
        if funding:
            parts.append(f"The company has raised {funding}")
        if latest:
            parts.append(f"({latest})")
        
        # Employees
        employees = competitor.get("employee_count")
        if employees:
            parts.append(f"and employs approximately {employees} people")
        
        # Threat assessment
        threat = competitor.get("threat_level")
        if threat:
            threat_text = {
                "High": "a direct competitive threat",
                "Medium": "a notable market presence",
                "Low": "minimal competitive overlap"
            }
            parts.append(f"representing {threat_text.get(threat, 'a competitor')}")
        
        # Combine into paragraph
        summary = ". ".join(parts) + "."
        summary = summary.replace(". .", ".").replace("  ", " ")
        
        return summary
    
    def generate_battlecard_summary(self, competitor: Dict[str, Any]) -> Dict[str, str]:
        """Generate battlecard-style summary sections."""
        return {
            "overview": self.generate_summary(competitor),
            "strengths": self._extract_strengths(competitor),
            "weaknesses": self._extract_weaknesses(competitor),
            "key_differentiators": self._extract_differentiators(competitor),
            "common_objections": self._generate_objections(competitor),
        }
    
    def _extract_strengths(self, comp: Dict) -> str:
        strengths = []
        
        if comp.get("customer_count") and "000" in str(comp.get("customer_count")):
            strengths.append("Large customer base")
        if comp.get("funding_total") and "$" in str(comp.get("funding_total")):
            strengths.append("Well-funded")
        if "ai" in (comp.get("recent_launches") or "").lower():
            strengths.append("Investing in AI/innovation")
        if float(comp.get("g2_rating") or 0) >= 4.5:
            strengths.append("High customer satisfaction")
        
        return "; ".join(strengths) if strengths else "No significant strengths identified"
    
    def _extract_weaknesses(self, comp: Dict) -> str:
        weaknesses = []
        
        if float(comp.get("g2_rating") or 5) < 4.0:
            weaknesses.append("Lower customer satisfaction scores")
        if "enterprise" in (comp.get("customer_size_focus") or "").lower():
            weaknesses.append("May not serve smaller practices well")
        if "custom" in (comp.get("base_price") or "").lower():
            weaknesses.append("Opaque pricing")
        
        return "; ".join(weaknesses) if weaknesses else "Limited public weaknesses identified"
    
    def _extract_differentiators(self, comp: Dict) -> str:
        features = comp.get("key_features") or ""
        if "telehealth" in features.lower():
            return "Integrated telehealth capabilities"
        elif "ai" in features.lower():
            return "AI-powered features"
        elif "kiosk" in features.lower():
            return "Self-service kiosk hardware"
        return "General patient engagement platform"
    
    def _generate_objections(self, comp: Dict) -> str:
        name = comp.get("name", "Competitor")
        return f"'Why not {name}?' - Focus on Certify's specific strengths in your target segment."


# ============== Dashboard AI Insights ==============

class DashboardInsightGenerator:
    """
    Generates high-level executive insights for the entire dashboard.

    v5.0.2: Supports both OpenAI and Gemini providers with hybrid routing.
    """

    def __init__(self):
        self.client = None
        self.gemini_extractor = None
        self.provider = os.getenv("AI_PROVIDER", "hybrid")

        # Initialize OpenAI
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.client = OpenAI(api_key=api_key)
        except ImportError:
            pass

        # Initialize Gemini (v5.0.2)
        try:
            from gemini_provider import GeminiExtractor
            if os.getenv("GOOGLE_AI_API_KEY"):
                self.gemini_extractor = GeminiExtractor()
        except ImportError:
            pass

    @property
    def has_openai(self) -> bool:
        """Check if OpenAI is available."""
        return self.client is not None

    @property
    def has_gemini(self) -> bool:
        """Check if Gemini is available."""
        return self.gemini_extractor is not None and self.gemini_extractor.is_available

    def get_active_provider(self) -> str:
        """Determine which provider to use for summaries."""
        if self.provider == "openai" and self.has_openai:
            return "openai"
        elif self.provider == "gemini" and self.has_gemini:
            return "gemini"
        elif self.provider == "hybrid":
            # For executive summaries, prefer quality (OpenAI) but fallback to Gemini
            quality_pref = os.getenv("AI_QUALITY_TASKS", "openai")
            if quality_pref == "openai" and self.has_openai:
                return "openai"
            elif quality_pref == "gemini" and self.has_gemini:
                return "gemini"
            # Fallback chain
            return "openai" if self.has_openai else ("gemini" if self.has_gemini else "none")

        # Fallback to whatever is available
        return "openai" if self.has_openai else ("gemini" if self.has_gemini else "none")

    def generate_insight(self, competitors: List[Dict[str, Any]], custom_prompt: Optional[str] = None) -> Dict[str, str]:
        """
        Generate an executive summary and actionable insights.

        v5.0.2: Supports hybrid AI routing between OpenAI and Gemini.
        """
        active_provider = self.get_active_provider()

        # Fallback if no AI
        if active_provider == "none":
            return self._generate_fallback_summary(competitors)

        # Prepare context
        context = self._prepare_context(competitors)

        system_prompt = custom_prompt or "You are a Chief Strategy Officer. Analyze the competitive landscape data provided and generate a concise executive summary (2-3 sentences) and 3 bullet points of actionable strategic advice for 'Certify Health' (our company). Focus on threats, pricing pressure, and feature gaps."

        try:
            if active_provider == "gemini":
                return self._generate_with_gemini(competitors, system_prompt)
            else:
                return self._generate_with_openai(context, system_prompt)
        except Exception as e:
            print(f"AI Insight Error ({active_provider}): {e}")
            # Try fallback provider
            fallback_enabled = os.getenv("AI_FALLBACK_ENABLED", "true").lower() == "true"
            if fallback_enabled:
                try:
                    if active_provider == "openai" and self.has_gemini:
                        return self._generate_with_gemini(competitors, system_prompt)
                    elif active_provider == "gemini" and self.has_openai:
                        return self._generate_with_openai(context, system_prompt)
                except Exception as fallback_error:
                    print(f"Fallback AI Error: {fallback_error}")

            return self._generate_fallback_summary(competitors)

    def _generate_with_openai(self, context: str, system_prompt: str) -> Dict[str, str]:
        """Generate summary using OpenAI."""
        response = self.client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Competitive Landscape Data:\n{context}"}
            ],
            temperature=0.7,
            max_tokens=500
        )
        content = response.choices[0].message.content
        result = self._parse_ai_response(content)
        result["provider"] = "openai"
        result["model"] = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return result

    def _generate_with_gemini(self, competitors: List[Dict[str, Any]], custom_prompt: str) -> Dict[str, str]:
        """Generate summary using Gemini."""
        summary = self.gemini_extractor.generate_executive_summary(
            competitor_data=competitors,
            custom_prompt=custom_prompt,
        )
        return {
            "summary": summary,
            "type": "ai",
            "provider": "gemini",
            "model": self.gemini_extractor.provider.config.model
        }

    def _prepare_context(self, competitors: List[Dict[str, Any]]) -> str:
        lines = []
        for c in competitors:
            lines.append(f"- {c.get('name')}: Threat={c.get('threat_level')}, Price={c.get('base_price')}, Focus={c.get('target_segments')}, Key Feature={c.get('key_features', '')[:50]}...")
        return "\n".join(lines)

    def _parse_ai_response(self, content: str) -> Dict[str, str]:
        # Simple parsing or return raw text
        # We'll return raw markdown for now
        return {
            "summary": content,
            "type": "ai"
        }

    def _generate_fallback_summary(self, competitors: List[Dict[str, Any]]) -> Dict[str, str]:
        count = len(competitors)
        high_threat = sum(1 for c in competitors if c.get('threat_level', '').upper() == 'HIGH')
        return {
            "summary": f"### Executive Brief (Automated)\n\nWe are currently tracking **{count} competitors**, of which **{high_threat} are High Threat**. \n\n**Actionable Insights:**\n- Monitor pricing changes weekly.\n- Investigate feature gaps in patient intake.\n- Review battlecards for high-threat targets.",
            "type": "fallback"
        }


# ============== Master Analytics Engine ==============

class AnalyticsEngine:
    """Main analytics engine combining all analysis capabilities."""
    
    def __init__(self):
        self.threat_calculator = ThreatScoreCalculator()
        self.market_estimator = MarketShareEstimator()
        self.feature_analyzer = FeatureAnalyzer()
        self.heatmap_generator = CompetitiveHeatmap()
        self.summarizer = CompetitorSummarizer()
        self.insight_generator = DashboardInsightGenerator()
    
    def full_analysis(self, competitor: Dict[str, Any]) -> Dict[str, Any]:
        """Run full analysis on a competitor."""
        threat_score = self.threat_calculator.calculate(competitor)
        market_share = self.market_estimator.estimate(competitor)
        feature_gaps = self.feature_analyzer.analyze(competitor)
        feature_summary = self.feature_analyzer.summarize_gaps(feature_gaps)
        summary = self.summarizer.generate_summary(competitor)
        battlecard = self.summarizer.generate_battlecard_summary(competitor)
        
        return {
            "competitor": competitor.get("name"),
            "threat_score": asdict(threat_score),
            "market_share": asdict(market_share),
            "feature_analysis": {
                "gaps": [asdict(g) for g in feature_gaps],
                "summary": feature_summary
            },
            "ai_summary": summary,
            "battlecard": battlecard,
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    def comparative_analysis(self, competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run comparative analysis across multiple competitors."""
        analyses = [self.full_analysis(c) for c in competitors]
        heatmap = self.heatmap_generator.generate_heatmap_data(competitors)
        
        # Rankings
        by_threat = sorted(analyses, key=lambda x: x["threat_score"]["overall_score"], reverse=True)
        by_market = sorted(analyses, key=lambda x: x["market_share"]["estimated_share"], reverse=True)
        
        # AI Executive Summary
        executive_insight = self.insight_generator.generate_insight(competitors)
        
        return {
            "individual_analyses": analyses,
            "heatmap": heatmap,
            "rankings": {
                "by_threat": [a["competitor"] for a in by_threat],
                "by_market_share": [a["competitor"] for a in by_market],
            },
            "executive_summary": executive_insight,
            "total_competitors": len(competitors),
            "analyzed_at": datetime.utcnow().isoformat()
        }


# Test function
def test_analytics():
    """Test analytics engine."""
    test_competitor = {
        "name": "Phreesia",
        "target_segments": "Health Systems; Large Practices",
        "customer_size_focus": "Large (50+)",
        "funding_total": "$300M+",
        "employee_growth_rate": "15% YoY",
        "product_categories": "Intake; Payments; Scheduling",
        "customer_count": "3000+",
        "base_price": "$3.00",
        "pricing_model": "Per Visit",
        "recent_launches": "AI-powered intake (2024)",
        "key_features": "Digital intake, Eligibility verification, Patient payments",
        "g2_rating": "4.5",
        "year_founded": "2005",
        "headquarters": "Raleigh, NC",
        "employee_count": "1500+",
        "threat_level": "High",
        "latest_round": "Public (NYSE: PHR)",
    }
    
    engine = AnalyticsEngine()
    # Mock list for comparative
    result = engine.comparative_analysis([test_competitor])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    test_analytics()
