"""
Certify Intel - AI-Powered Threat Analyzer
Automatically calculates threat scores using GPT-4 analysis.
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# OpenAI import (optional)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class ThreatAssessment:
    """Result of threat analysis."""
    score: int  # 0-100
    level: str  # High/Medium/Low
    reasoning: str
    key_risks: List[str]
    competitive_advantages: List[str]
    recommended_actions: List[str]
    confidence: float
    analyzed_at: str


class ThreatAnalyzer:
    """AI-powered competitive threat analyzer."""
    
    # Certify Health's core capabilities for comparison
    CERTIFY_CAPABILITIES = [
        "Patient intake and digital check-in",
        "Eligibility verification",
        "Patient payments and billing",
        "Biometric authentication",
        "EHR integration",
        "Insurance verification",
        "Patient engagement",
        "Self-service kiosks"
    ]
    
    def __init__(self, use_openai: bool = True):
        self.use_openai = use_openai and OPENAI_AVAILABLE
        self.client = None
        
        if self.use_openai:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.client = OpenAI(api_key=api_key)
    
    def analyze_threat(self, competitor: Dict[str, Any]) -> ThreatAssessment:
        """
        Analyze a competitor's threat level using AI.
        
        Args:
            competitor: Competitor data dictionary
            
        Returns:
            ThreatAssessment with score and analysis
        """
        if self.client:
            return self._ai_analysis(competitor)
        else:
            return self._heuristic_analysis(competitor)
    
    def _ai_analysis(self, competitor: Dict[str, Any]) -> ThreatAssessment:
        """Use GPT-4 for threat analysis."""
        prompt = self._build_analysis_prompt(competitor)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a competitive intelligence analyst for Certify Health, 
                        a healthcare technology company specializing in patient intake, eligibility verification, 
                        patient payments, and biometric authentication. Analyze competitors objectively."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return ThreatAssessment(
                score=min(100, max(0, result.get("threat_score", 50))),
                level=self._score_to_level(result.get("threat_score", 50)),
                reasoning=result.get("reasoning", "Analysis complete"),
                key_risks=result.get("key_risks", []),
                competitive_advantages=result.get("competitive_advantages", []),
                recommended_actions=result.get("recommended_actions", []),
                confidence=result.get("confidence", 0.8),
                analyzed_at=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            print(f"AI analysis failed: {e}")
            return self._heuristic_analysis(competitor)
    
    def _heuristic_analysis(self, competitor: Dict[str, Any]) -> ThreatAssessment:
        """Fallback heuristic-based threat analysis."""
        score = 50  # Start neutral
        risks = []
        advantages = []
        
        # Factor 1: Funding (indicates resources)
        funding = str(competitor.get("funding_total", "")).lower()
        if "public" in funding or "ipo" in funding:
            score += 15
            risks.append("Public company with significant resources")
        elif any(x in funding for x in ["$100m", "$200m", "$300m", "$400m", "$500m"]):
            score += 12
            risks.append("Well-funded with $100M+ raised")
        elif "$" in funding:
            score += 5
        
        # Factor 2: Customer count (market traction)
        customers = str(competitor.get("customer_count", "0"))
        customers_clean = ''.join(filter(str.isdigit, customers.split('+')[0].split(',')[0]))
        if customers_clean:
            num_customers = int(customers_clean)
            if num_customers > 10000:
                score += 15
                risks.append(f"Large customer base ({customers})")
            elif num_customers > 1000:
                score += 10
                risks.append("Growing customer base")
            elif num_customers > 100:
                score += 5
        
        # Factor 3: Employee count (execution capacity)
        employees = str(competitor.get("employee_count", "0"))
        emp_clean = ''.join(filter(str.isdigit, employees.split('+')[0].split('-')[0]))
        if emp_clean:
            num_employees = int(emp_clean)
            if num_employees > 1000:
                score += 10
                risks.append("Large workforce for rapid execution")
            elif num_employees > 200:
                score += 5
        
        # Factor 4: Product overlap
        products = str(competitor.get("product_categories", "")).lower()
        features = str(competitor.get("key_features", "")).lower()
        combined = products + " " + features
        
        overlap_count = 0
        for capability in self.CERTIFY_CAPABILITIES:
            if any(word in combined for word in capability.lower().split()):
                overlap_count += 1
        
        if overlap_count >= 5:
            score += 15
            risks.append(f"High product overlap ({overlap_count}/8 capabilities)")
        elif overlap_count >= 3:
            score += 8
            risks.append(f"Moderate product overlap ({overlap_count}/8 capabilities)")
        elif overlap_count >= 1:
            score += 3
        
        # Factor 5: G2 Rating (market perception)
        g2_rating = competitor.get("g2_rating")
        if g2_rating:
            try:
                rating = float(str(g2_rating).replace('+', ''))
                if rating >= 4.5:
                    score += 8
                    risks.append(f"Excellent market reputation ({rating} G2 rating)")
                elif rating >= 4.0:
                    score += 4
            except:
                pass
        
        # Factor 6: Target segments overlap
        segments = str(competitor.get("target_segments", "")).lower()
        if any(x in segments for x in ["health system", "hospital", "physician", "specialty"]):
            score += 5
            risks.append("Targets same healthcare segments")
        
        # Calculate Certify advantages (inverse of threats)
        if overlap_count < 3:
            advantages.append("Limited product feature overlap")
        if "biometric" not in combined:
            advantages.append("Certify's biometric authentication is unique")
        if score < 60:
            advantages.append("Lower competitive pressure allows focused growth")
        
        # Cap score
        score = min(100, max(0, score))
        
        # Generate recommended actions
        actions = self._generate_actions(score, risks)
        
        return ThreatAssessment(
            score=score,
            level=self._score_to_level(score),
            reasoning=f"Heuristic analysis based on {len(risks)} risk factors identified.",
            key_risks=risks[:5],
            competitive_advantages=advantages[:3],
            recommended_actions=actions,
            confidence=0.7,
            analyzed_at=datetime.utcnow().isoformat()
        )
    
    def _build_analysis_prompt(self, competitor: Dict[str, Any]) -> str:
        """Build the GPT analysis prompt."""
        return f"""
Analyze this competitor's threat level to Certify Health:

COMPETITOR DATA:
- Name: {competitor.get('name', 'Unknown')}
- Website: {competitor.get('website', 'N/A')}
- Products: {competitor.get('product_categories', 'Unknown')}
- Key Features: {competitor.get('key_features', 'Unknown')}
- Target Segments: {competitor.get('target_segments', 'Unknown')}
- Customer Count: {competitor.get('customer_count', 'Unknown')}
- Employee Count: {competitor.get('employee_count', 'Unknown')}
- Funding: {competitor.get('funding_total', 'Unknown')}
- G2 Rating: {competitor.get('g2_rating', 'Unknown')}
- Pricing: {competitor.get('pricing_model', 'Unknown')} - {competitor.get('base_price', 'Unknown')}

CERTIFY HEALTH CAPABILITIES:
{chr(10).join(f"- {cap}" for cap in self.CERTIFY_CAPABILITIES)}

Provide a threat analysis in JSON format:
{{
    "threat_score": <0-100>,
    "reasoning": "<2-3 sentence summary>",
    "key_risks": ["<risk1>", "<risk2>", "<risk3>"],
    "competitive_advantages": ["<advantage1>", "<advantage2>"],
    "recommended_actions": ["<action1>", "<action2>", "<action3>"],
    "confidence": <0.0-1.0>
}}
"""
    
    def _score_to_level(self, score: int) -> str:
        """Convert numeric score to threat level."""
        if score >= 70:
            return "High"
        elif score >= 40:
            return "Medium"
        else:
            return "Low"
    
    def _generate_actions(self, score: int, risks: List[str]) -> List[str]:
        """Generate recommended actions based on threat level."""
        actions = []
        
        if score >= 70:
            actions.append("Monitor this competitor weekly")
            actions.append("Prepare defensive positioning for sales team")
            actions.append("Identify and reinforce competitive differentiators")
        elif score >= 40:
            actions.append("Include in monthly competitive review")
            actions.append("Track product announcements and pricing changes")
        else:
            actions.append("Quarterly review sufficient")
        
        if any("fund" in r.lower() for r in risks):
            actions.append("Watch for aggressive market expansion")
        
        if any("customer" in r.lower() for r in risks):
            actions.append("Strengthen customer retention programs")
        
        return actions[:4]
    
    def batch_analyze(self, competitors: List[Dict[str, Any]]) -> List[ThreatAssessment]:
        """Analyze multiple competitors."""
        return [self.analyze_threat(c) for c in competitors]


# Convenience function for API use
def analyze_competitor_threat(competitor_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a competitor's threat level.
    
    Args:
        competitor_data: Dictionary with competitor fields
        
    Returns:
        Dict with threat assessment
    """
    analyzer = ThreatAnalyzer(use_openai=True)
    assessment = analyzer.analyze_threat(competitor_data)
    
    return {
        "score": assessment.score,
        "level": assessment.level,
        "reasoning": assessment.reasoning,
        "key_risks": assessment.key_risks,
        "competitive_advantages": assessment.competitive_advantages,
        "recommended_actions": assessment.recommended_actions,
        "confidence": assessment.confidence,
        "analyzed_at": assessment.analyzed_at
    }


if __name__ == "__main__":
    # Test with sample competitor
    test_competitor = {
        "name": "Phreesia",
        "website": "https://phreesia.com",
        "product_categories": "Patient intake, Payment collection, Clinical support",
        "key_features": "Digital check-in, Insurance verification, Patient payments",
        "target_segments": "Health systems, Physician practices",
        "customer_count": "3500+",
        "employee_count": "1800+",
        "funding_total": "Public (NYSE: PHR)",
        "g2_rating": "4.3"
    }
    
    result = analyze_competitor_threat(test_competitor)
    print(json.dumps(result, indent=2))
