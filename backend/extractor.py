"""
Certify Intel - AI Data Extraction (v5.0.2)
Uses OpenAI GPT or Google Gemini to extract structured competitor data from scraped content.

Supports hybrid mode with automatic routing based on task type and cost optimization.
"""
import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI not installed. Run: pip install openai")

# Gemini support (v5.0.2)
try:
    from gemini_provider import GeminiExtractor, AIRouter, get_ai_router
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    GeminiExtractor = None
    AIRouter = None


@dataclass
class ExtractedData:
    """Structured data extracted from competitor website."""
    
    # Pricing
    pricing_model: Optional[str] = None
    base_price: Optional[str] = None
    price_unit: Optional[str] = None
    
    # Product
    product_categories: Optional[str] = None
    key_features: Optional[str] = None
    integration_partners: Optional[str] = None
    certifications: Optional[str] = None
    
    # Market
    target_segments: Optional[str] = None
    customer_size_focus: Optional[str] = None
    geographic_focus: Optional[str] = None
    customer_count: Optional[str] = None
    key_customers: Optional[str] = None
    
    # Company
    employee_count: Optional[str] = None
    year_founded: Optional[str] = None
    headquarters: Optional[str] = None
    funding_total: Optional[str] = None
    
    # Digital
    recent_launches: Optional[str] = None
    
    # Metadata
    confidence_score: Optional[int] = None
    extraction_notes: Optional[str] = None


@dataclass
class FieldSourceInfo:
    """Source information for a single extracted field."""
    value: str
    source_page: str  # "homepage", "pricing", "about", etc.
    source_url: str
    extraction_context: Optional[str] = None  # Snippet showing where value was found
    confidence: int = 40  # 0-100 confidence score


@dataclass
class ExtractedDataWithSource:
    """Enhanced extraction result with full provenance for each field."""

    # Existing fields (same as ExtractedData)
    pricing_model: Optional[str] = None
    base_price: Optional[str] = None
    price_unit: Optional[str] = None
    product_categories: Optional[str] = None
    key_features: Optional[str] = None
    integration_partners: Optional[str] = None
    certifications: Optional[str] = None
    target_segments: Optional[str] = None
    customer_size_focus: Optional[str] = None
    geographic_focus: Optional[str] = None
    customer_count: Optional[str] = None
    key_customers: Optional[str] = None
    employee_count: Optional[str] = None
    year_founded: Optional[str] = None
    headquarters: Optional[str] = None
    funding_total: Optional[str] = None
    recent_launches: Optional[str] = None
    confidence_score: Optional[int] = None
    extraction_notes: Optional[str] = None

    # NEW: Source metadata for each field
    field_sources: Dict[str, FieldSourceInfo] = field(default_factory=dict)
    # Structure: {
    #     "customer_count": FieldSourceInfo(
    #         value="3000+",
    #         source_page="about",
    #         source_url="https://phreesia.com/about",
    #         extraction_context="Found in text: 'Trusted by 3,000+ healthcare organizations'",
    #         confidence=65
    #     )
    # }

    # NEW: Extraction metadata
    extraction_timestamp: Optional[datetime] = None
    extraction_model: Optional[str] = None  # "gpt-4o-mini"
    total_pages_scraped: int = 0
    extraction_warnings: List[str] = field(default_factory=list)
    pages_scraped: List[str] = field(default_factory=list)  # ["homepage", "pricing", "about"]


class GPTExtractor:
    """Uses GPT to extract structured data from website content."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = None
        
        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
    
    def extract_from_content(self, competitor_name: str, content: str, page_type: str = "homepage") -> ExtractedData:
        """Extract structured data from page content using GPT."""
        
        if not self.client:
            return ExtractedData(
                extraction_notes="OpenAI client not available. Set OPENAI_API_KEY environment variable."
            )
        
        # Truncate content if too long
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        
        prompt = self._build_extraction_prompt(competitor_name, content, page_type)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return self._parse_result(result)
            
        except Exception as e:
            return ExtractedData(
                extraction_notes=f"Extraction failed: {str(e)}"
            )
    
    def _get_system_prompt(self) -> str:
        """System prompt for the extraction agent."""
        return """You are a competitive intelligence analyst specializing in healthcare IT companies.
Your task is to extract structured data from competitor websites.
Be precise and only extract information that is clearly stated.
If information is not available, use null.
For pricing, look for specific numbers, not vague ranges.
For features, focus on product capabilities relevant to patient intake, eligibility verification, payments, and patient engagement.

Always respond with valid JSON matching the requested schema."""

    def _build_extraction_prompt(self, competitor_name: str, content: str, page_type: str) -> str:
        """Build the extraction prompt based on page type."""
        
        # 1. PRICING PAGE PROMPT
        if page_type == "pricing":
            return f"""Analyze this PRICING page for {competitor_name}.
Extract the following pricing details. Be extremely specific with numbers.
Return JSON:
{{
    "pricing_model": "Describe the model (e.g., 'Per Provider/Month', 'Per Visit', 'Platform Fee'). Look for tiers.",
    "base_price": "Lowest numeric price found (e.g., '$299'). Include currency symbol.",
    "price_unit": "The unit for the base price (e.g., 'per month', 'per provider', 'one-time').",
    "free_trial": "True/False if mentioned",
    "setup_fee": "Implementation or setup fee if mentioned",
    "confidence_score": "Confidence 1-100",
    "extraction_notes": "Quote the text where price was found"
}}

CONTENT:
{content}"""

        # 2. FEATURES/PRODUCT PAGE PROMPT
        elif page_type == "features" or page_type == "product":
            return f"""Analyze this FEATURES page for {competitor_name}.
Identify key capabilities relevant to healthcare patient engagement.
Return JSON:
{{
    "product_categories": "High-level categories (e.g., 'Intake', 'Payments', 'Telehealth'). Semicolon-separated.",
    "key_features": "List specific features (e.g., 'Mobile Check-in', 'Real-time Eligibility', 'Biometric Auth'). Comma-separated.",
    "integration_partners": "List EHRs/PMs mentioned (e.g., Epic, Cerner, Athena). Semicolon-separated.",
    "certifications": "Security certs (HIPAA, SOC2, etc.) if mentioned.",
    "confidence_score": "Confidence 1-100",
    "extraction_notes": "Notes on feature availability"
}}

CONTENT:
{content}"""

        # 3. ABOUT/CUSTOMERS PAGE PROMPT
        elif page_type == "about" or page_type == "customers":
            return f"""Analyze this ABOUT/CUSTOMERS page for {competitor_name}.
Extract company and market data.
Return JSON:
{{
    "year_founded": "Year founded",
    "headquarters": "City, State, Country",
    "employee_count": "Number of employees",
    "customer_count": "Number of customers/providers/users",
    "key_customers": "List specific health system or client names",
    "target_segments": "Who they serve (e.g. 'Large Health Systems', 'Small Practices')",
    "geographic_focus": "Regions served",
    "funding_total": "Total funding or investment details",
    "confidence_score": "Confidence 1-100",
    "extraction_notes": "Notes on company data"
}}

CONTENT:
{content}"""

        # 4. DEFAULT/HOMEPAGE PROMPT (General Fallback)
        else:
            return f"""Analyze this GENERAL content from {competitor_name}'s {page_type} page.
Extract as much structured data as possible. Use null if not found.
Return JSON:
{{
    "pricing_model": "How they charge (e.g., 'Per Visit', 'Per Provider', 'Per Location', 'Subscription', 'Custom')",
    "base_price": "Starting price with currency symbol (e.g., '$3.00', '$199/month')",
    "price_unit": "Unit of pricing (e.g., 'per visit', 'per provider/month')",
    "product_categories": "Product types separated by semicolons (e.g., 'Patient Intake; Payments; Scheduling')",
    "key_features": "Main features, comma-separated",
    "integration_partners": "EHR/PM systems they integrate with, semicolon-separated",
    "certifications": "Security certifications (e.g., 'HIPAA; SOC2; HITRUST')",
    "target_segments": "Customer segments (e.g., 'Health Systems; Specialty Practices')",
    "customer_size_focus": "Practice size focus (e.g., 'Small (1-15)', 'Medium (15-50)', 'Large (50+)')",
    "geographic_focus": "Geographic markets",
    "customer_count": "Number of customers if mentioned",
    "key_customers": "Notable customer names if mentioned",
    "employee_count": "Employee count if mentioned",
    "year_founded": "Year company was founded",
    "headquarters": "Company headquarters location",
    "funding_total": "Total funding raised if mentioned",
    "recent_launches": "Recent product announcements",
    "confidence_score": "Your confidence in the extraction (1-100)",
    "extraction_notes": "Any notes about the extraction or data quality"
}}

CONTENT TO ANALYZE:
{content}"""
    
    def _parse_result(self, result: Dict[str, Any]) -> ExtractedData:
        """Parse GPT response into ExtractedData."""
        return ExtractedData(
            pricing_model=result.get("pricing_model"),
            base_price=result.get("base_price"),
            price_unit=result.get("price_unit"),
            product_categories=result.get("product_categories"),
            key_features=result.get("key_features"),
            integration_partners=result.get("integration_partners"),
            certifications=result.get("certifications"),
            target_segments=result.get("target_segments"),
            customer_size_focus=result.get("customer_size_focus"),
            geographic_focus=result.get("geographic_focus"),
            customer_count=result.get("customer_count"),
            key_customers=result.get("key_customers"),
            employee_count=result.get("employee_count"),
            year_founded=result.get("year_founded"),
            headquarters=result.get("headquarters"),
            funding_total=result.get("funding_total"),
            recent_launches=result.get("recent_launches"),
            confidence_score=result.get("confidence_score"),
            extraction_notes=result.get("extraction_notes")
        )
    
    def merge_extractions(self, extractions: List[ExtractedData]) -> ExtractedData:
        """Merge multiple extractions (from different pages) into one."""
        if not extractions:
            return ExtractedData()

        merged = ExtractedData()

        # For each field, take the first non-None value
        for extraction in extractions:
            for field in ExtractedData.__dataclass_fields__:
                if getattr(merged, field) is None:
                    value = getattr(extraction, field)
                    if value is not None:
                        setattr(merged, field, value)

        return merged

    def extract_products_and_pricing(self, competitor_name: str, content: str) -> Dict[str, Any]:
        """
        Extract product-level pricing from content.
        Returns structured data about multiple products and their pricing tiers.

        This is for Phase 3 of Data Quality Enhancement.
        """
        if not self.client:
            return {
                "products": [],
                "error": "OpenAI client not available. Set OPENAI_API_KEY environment variable."
            }

        # Truncate content if too long
        max_content_length = 12000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        prompt = f"""Analyze this content from {competitor_name} and extract ALL products/solutions and their pricing.

Healthcare SaaS pricing models to look for:
- per_visit: Charge per patient encounter (e.g., "$3.00/visit")
- per_provider: Monthly fee per provider (e.g., "$400/provider/month")
- per_location: Fee per practice location (e.g., "$1,500/location/month")
- subscription_flat: Fixed monthly fee (e.g., "$299/month")
- subscription_tiered: Tiered by features (e.g., "Basic $99, Pro $299, Enterprise $499")
- percentage_collections: % of collected revenue (e.g., "4-8% of collections")
- custom_enterprise: Negotiated pricing ("Contact Sales")

Return JSON with this EXACT structure:
{{
    "products": [
        {{
            "product_name": "Name of the product/solution",
            "product_category": "One of: Patient Intake, Patient Payments, RCM, Practice Management, EHR, Telehealth, Patient Engagement, Scheduling, Analytics",
            "target_segment": "SMB, Mid-Market, or Enterprise",
            "is_primary_product": true/false,
            "pricing_tiers": [
                {{
                    "tier_name": "Basic/Professional/Enterprise or similar",
                    "tier_position": 1,
                    "pricing_model": "per_visit|per_provider|per_location|subscription_flat|subscription_tiered|percentage_collections|custom_enterprise",
                    "base_price": 3.00,
                    "price_currency": "USD",
                    "price_unit": "visit|provider/month|location/month|month",
                    "price_display": "$3.00/visit",
                    "percentage_rate": null,
                    "setup_fee": null,
                    "contract_length": "Monthly|Annual|Multi-year",
                    "included_features": ["Feature 1", "Feature 2"]
                }}
            ],
            "key_features": ["Feature 1", "Feature 2"]
        }}
    ],
    "extraction_confidence": 1-100,
    "extraction_notes": "Notes about the extraction quality or missing data"
}}

IMPORTANT:
- If a product has multiple tiers (Basic, Pro, Enterprise), list each as a separate pricing_tier
- If pricing says "Contact Sales" or "Custom", use pricing_model: "custom_enterprise" and base_price: null
- If you see "Starting at $X", use that as the base price for the first tier
- Extract actual numbers, not ranges (use the lowest number in a range)
- If no specific products are identifiable, create a single product named "{competitor_name} Platform"

CONTENT TO ANALYZE:
{content}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": """You are a healthcare IT pricing analyst.
Extract product and pricing information with precision.
Focus on identifying:
1. Individual products/solutions (not just company-level info)
2. Specific pricing tiers and models
3. Healthcare-specific pricing patterns (per visit, per provider, etc.)
Always respond with valid JSON matching the requested schema."""},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            return {
                "products": [],
                "error": f"Extraction failed: {str(e)}"
            }

    def extract_feature_matrix(self, competitor_name: str, product_name: str, content: str) -> Dict[str, Any]:
        """
        Extract feature matrix for a specific product.
        Returns features organized by category with availability status.
        """
        if not self.client:
            return {
                "features": [],
                "error": "OpenAI client not available."
            }

        max_content_length = 10000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        prompt = f"""Analyze this content for {competitor_name}'s {product_name} product.
Extract ALL features mentioned and categorize them.

Feature categories for healthcare IT:
- Patient Intake: Check-in, forms, consent
- Payments: Processing, collections, billing
- Integration: EHR/PM connectivity
- Security: HIPAA, certifications
- Scheduling: Appointments, reminders
- Communication: Patient messaging, portals
- Analytics: Reporting, dashboards

Return JSON:
{{
    "features": [
        {{
            "feature_category": "Patient Intake",
            "feature_name": "Digital Check-In",
            "feature_status": "included|add_on|not_available|coming_soon",
            "feature_tier": "Basic|Professional|Enterprise|All",
            "notes": "Any specific notes"
        }}
    ],
    "extraction_confidence": 1-100
}}

CONTENT:
{content}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a healthcare IT feature analyst. Extract detailed feature information."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            return {
                "features": [],
                "error": f"Extraction failed: {str(e)}"
            }


# ============== PHASE 5: ENHANCED EXTRACTOR WITH SOURCE TRACKING ==============

class EnhancedGPTExtractor:
    """
    GPT extractor with full source tracking for each extracted field.
    Phase 5 implementation for data quality enhancement.
    """

    # Confidence scoring based on page type and field relevance
    CONFIDENCE_MATRIX = {
        # (page_type, field_name) -> base confidence
        ("pricing", "base_price"): 75,
        ("pricing", "pricing_model"): 75,
        ("pricing", "price_unit"): 70,
        ("about", "customer_count"): 65,
        ("about", "employee_count"): 65,
        ("about", "year_founded"): 80,
        ("about", "headquarters"): 80,
        ("customers", "customer_count"): 70,
        ("customers", "key_customers"): 75,
        ("features", "key_features"): 70,
        ("features", "product_categories"): 65,
        ("integrations", "integration_partners"): 75,
        ("homepage", "target_segments"): 50,
        ("homepage", "customer_count"): 55,
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = None

        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(api_key=self.api_key)

    def extract_with_sources(
        self,
        competitor_name: str,
        competitor_website: str,
        page_contents: Dict[str, str]  # {"homepage": content, "pricing": content, ...}
    ) -> ExtractedDataWithSource:
        """
        Extract data from multiple pages and track which page each data point came from.

        Args:
            competitor_name: Name of the competitor
            competitor_website: Base URL of the competitor's website
            page_contents: Dict mapping page type to scraped content

        Returns:
            ExtractedDataWithSource with field-level source tracking
        """
        result = ExtractedDataWithSource()
        result.extraction_timestamp = datetime.utcnow()
        result.extraction_model = self.model
        result.total_pages_scraped = len(page_contents)
        result.pages_scraped = list(page_contents.keys())

        if not self.client:
            result.extraction_warnings.append("OpenAI client not available")
            return result

        # Extract from each page and merge results
        for page_type, content in page_contents.items():
            if not content or len(content.strip()) < 100:
                result.extraction_warnings.append(f"Page '{page_type}' has insufficient content")
                continue

            try:
                # Extract using existing GPT extractor logic
                extracted = self._extract_page(competitor_name, page_type, content)

                # Merge results, tracking source for each NEW field
                for field_name, value in extracted.items():
                    if value and field_name not in ["confidence_score", "extraction_notes"]:
                        # Only set if not already set (first extraction wins)
                        current_value = getattr(result, field_name, None)
                        if current_value is None and hasattr(result, field_name):
                            setattr(result, field_name, value)

                            # Build source URL
                            if page_type == "homepage":
                                source_url = competitor_website
                            else:
                                source_url = f"{competitor_website.rstrip('/')}/{page_type}"

                            # Get confidence for this field/page combination
                            confidence = self._estimate_confidence(page_type, field_name, content, value)

                            # Extract context snippet
                            context = self._get_context_snippet(content, str(value))

                            result.field_sources[field_name] = FieldSourceInfo(
                                value=str(value),
                                source_page=page_type,
                                source_url=source_url,
                                extraction_context=context,
                                confidence=confidence
                            )

            except Exception as e:
                result.extraction_warnings.append(f"Extraction failed for {page_type}: {str(e)}")

        # Calculate overall confidence as average of field confidences
        if result.field_sources:
            avg_confidence = sum(
                fs.confidence for fs in result.field_sources.values()
            ) / len(result.field_sources)
            result.confidence_score = int(avg_confidence)

        return result

    def _extract_page(self, competitor_name: str, page_type: str, content: str) -> Dict[str, Any]:
        """Extract data from a single page using GPT."""
        # Truncate content if too long
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        # Build prompt based on page type
        prompt = self._build_page_prompt(competitor_name, page_type, content)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            return {"extraction_notes": f"Error: {str(e)}"}

    def _get_system_prompt(self) -> str:
        """System prompt for extraction."""
        return """You are a competitive intelligence analyst specializing in healthcare IT companies.
Your task is to extract structured data from competitor websites.
Be precise and only extract information that is clearly stated.
If information is not available, use null.
For pricing, look for specific numbers, not vague ranges.
For features, focus on product capabilities relevant to patient intake, eligibility verification, payments, and patient engagement.
Always respond with valid JSON."""

    def _build_page_prompt(self, competitor_name: str, page_type: str, content: str) -> str:
        """Build extraction prompt based on page type."""

        base_schema = """
{
    "pricing_model": "Describe the model (e.g., 'Per Provider/Month', 'Per Visit')",
    "base_price": "Lowest numeric price found (e.g., '$299')",
    "price_unit": "The unit for the base price (e.g., 'per month', 'per provider')",
    "product_categories": "High-level categories separated by semicolons",
    "key_features": "Main features, comma-separated",
    "integration_partners": "EHR/PM systems, semicolon-separated",
    "certifications": "Security certifications (HIPAA, SOC2, etc.)",
    "target_segments": "Customer segments (e.g., 'Health Systems; Practices')",
    "customer_size_focus": "Practice size focus (e.g., 'Small', 'Enterprise')",
    "geographic_focus": "Geographic markets",
    "customer_count": "Number of customers if mentioned",
    "key_customers": "Notable customer names if mentioned",
    "employee_count": "Employee count if mentioned",
    "year_founded": "Year company was founded",
    "headquarters": "Company headquarters location",
    "funding_total": "Total funding raised if mentioned",
    "recent_launches": "Recent product announcements"
}"""

        page_focus = {
            "homepage": "Extract general company and product overview information.",
            "pricing": "Focus on extracting all pricing details, tiers, and pricing models.",
            "about": "Focus on company information: founding date, headquarters, employee count, customer count.",
            "customers": "Focus on customer count, key customer names, and case studies.",
            "features": "Focus on product features, capabilities, and integration partners.",
            "integrations": "Focus on EHR/PM integrations and technology partners.",
        }

        focus = page_focus.get(page_type, "Extract all available information.")

        return f"""Analyze this {page_type.upper()} page for {competitor_name}.
{focus}

Return JSON with only the fields where you found information (use null for others):
{base_schema}

CONTENT TO ANALYZE:
{content}"""

    def _estimate_confidence(
        self,
        page_type: str,
        field_name: str,
        content: str,
        value: Any
    ) -> int:
        """
        Estimate extraction confidence based on:
        1. Page type / field match (pricing page for prices = high)
        2. Whether the value appears verbatim in content
        3. Specificity of the value (exact numbers vs. vague descriptions)
        """
        # Start with matrix lookup or default
        base_confidence = self.CONFIDENCE_MATRIX.get(
            (page_type, field_name),
            40  # Default for unknown combinations
        )

        # Bonus for exact match in content
        if value and str(value) in content:
            base_confidence += 10

        # Bonus for specific numbers
        if value and any(c.isdigit() for c in str(value)):
            base_confidence += 5

        # Penalty for vague terms
        vague_terms = ["various", "many", "several", "some", "multiple", "custom", "contact"]
        if value and any(term in str(value).lower() for term in vague_terms):
            base_confidence -= 15

        return max(10, min(95, base_confidence))

    def _get_context_snippet(self, content: str, value: str, context_chars: int = 100) -> Optional[str]:
        """Extract a snippet showing where the value was found in content."""
        if not value or not content:
            return None

        # Try to find exact match
        idx = content.find(str(value))
        if idx == -1:
            # Try case-insensitive
            idx = content.lower().find(str(value).lower())

        if idx == -1:
            return None

        # Get surrounding context
        start = max(0, idx - context_chars // 2)
        end = min(len(content), idx + len(str(value)) + context_chars // 2)

        snippet = content[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

    def to_data_sources(
        self,
        result: ExtractedDataWithSource,
        competitor_id: int
    ) -> List[Dict[str, Any]]:
        """
        Convert extraction result to DataSource records for database storage.

        Returns a list of dicts ready to be inserted as DataSource rows.
        """
        from confidence_scoring import calculate_confidence_score, determine_confidence_level_from_score

        data_sources = []

        for field_name, source_info in result.field_sources.items():
            # Calculate confidence using Admiralty Code
            confidence_result = calculate_confidence_score(
                source_type="website_scrape",
                information_credibility=4,  # Plausible (from marketing content)
                data_age_days=0  # Fresh extraction
            )

            # Use the higher of GPT-estimated or Admiralty-calculated confidence
            final_confidence = max(source_info.confidence, confidence_result.score)

            data_sources.append({
                "competitor_id": competitor_id,
                "field_name": field_name,
                "current_value": source_info.value,
                "source_type": "website_scrape",
                "source_url": source_info.source_url,
                "source_name": f"Website - {source_info.source_page.title()}",
                "extraction_method": "gpt_extraction",
                "extracted_at": result.extraction_timestamp,
                "source_reliability": "D",  # Website = not usually reliable
                "information_credibility": 4,  # Plausible
                "confidence_score": final_confidence,
                "confidence_level": determine_confidence_level_from_score(final_confidence),
                "is_verified": False,
                "data_as_of_date": result.extraction_timestamp
            })

        return data_sources


# ============== PHASE 5.0.2: HYBRID EXTRACTOR ==============

class HybridExtractor:
    """
    Hybrid AI extractor that routes requests to OpenAI or Gemini based on configuration.

    Uses the AIRouter to determine the best provider for each task, with automatic
    fallback if the primary provider fails.

    v5.0.2 Implementation
    """

    def __init__(self, prefer_provider: Optional[str] = None):
        """
        Initialize hybrid extractor.

        Args:
            prefer_provider: Optional override ("openai" or "gemini")
        """
        self.prefer_provider = prefer_provider or os.getenv("AI_PROVIDER", "hybrid")

        # Initialize providers
        self.openai_extractor = None
        self.gemini_extractor = None

        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            self.openai_extractor = GPTExtractor()

        if GEMINI_AVAILABLE and GeminiExtractor and os.getenv("GOOGLE_AI_API_KEY"):
            self.gemini_extractor = GeminiExtractor()

    @property
    def is_available(self) -> bool:
        """Check if any AI provider is available."""
        openai_ok = self.openai_extractor is not None
        gemini_ok = self.gemini_extractor is not None and self.gemini_extractor.is_available
        return openai_ok or gemini_ok

    def get_provider(self, task_type: str = "data_extraction") -> str:
        """Determine which provider to use."""
        if self.prefer_provider == "openai" and self.openai_extractor:
            return "openai"
        elif self.prefer_provider == "gemini" and self.gemini_extractor and self.gemini_extractor.is_available:
            return "gemini"
        elif self.prefer_provider == "hybrid":
            # Use Gemini for bulk/extraction tasks (cheaper), OpenAI for quality tasks
            if task_type in ["bulk_extraction", "data_extraction", "news_analysis"]:
                if self.gemini_extractor and self.gemini_extractor.is_available:
                    return "gemini"
                elif self.openai_extractor:
                    return "openai"
            else:
                if self.openai_extractor:
                    return "openai"
                elif self.gemini_extractor and self.gemini_extractor.is_available:
                    return "gemini"

        # Fallback to whatever is available
        if self.openai_extractor:
            return "openai"
        elif self.gemini_extractor and self.gemini_extractor.is_available:
            return "gemini"

        return "none"

    def extract_from_content(
        self,
        competitor_name: str,
        content: str,
        page_type: str = "homepage"
    ) -> ExtractedData:
        """
        Extract structured data using the best available AI provider.

        Falls back to the secondary provider if the primary fails.
        """
        provider = self.get_provider("data_extraction")
        fallback_enabled = os.getenv("AI_FALLBACK_ENABLED", "true").lower() == "true"

        if provider == "gemini" and self.gemini_extractor:
            try:
                result = self.gemini_extractor.extract_from_content(
                    competitor_name, content, page_type
                )
                # Convert dict to ExtractedData
                if isinstance(result, dict):
                    return self._dict_to_extracted_data(result)
                return result
            except Exception as e:
                if fallback_enabled and self.openai_extractor:
                    return self.openai_extractor.extract_from_content(
                        competitor_name, content, page_type
                    )
                return ExtractedData(extraction_notes=f"Gemini extraction failed: {str(e)}")

        elif provider == "openai" and self.openai_extractor:
            try:
                return self.openai_extractor.extract_from_content(
                    competitor_name, content, page_type
                )
            except Exception as e:
                if fallback_enabled and self.gemini_extractor and self.gemini_extractor.is_available:
                    result = self.gemini_extractor.extract_from_content(
                        competitor_name, content, page_type
                    )
                    if isinstance(result, dict):
                        return self._dict_to_extracted_data(result)
                    return result
                return ExtractedData(extraction_notes=f"OpenAI extraction failed: {str(e)}")

        return ExtractedData(
            extraction_notes="No AI provider available. Set OPENAI_API_KEY or GOOGLE_AI_API_KEY."
        )

    def _dict_to_extracted_data(self, data: Dict[str, Any]) -> ExtractedData:
        """Convert a dictionary to ExtractedData dataclass."""
        # Filter to only valid ExtractedData fields
        valid_fields = {f.name for f in ExtractedData.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return ExtractedData(**filtered)

    def extract_products_and_pricing(
        self,
        competitor_name: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Extract product-level pricing using the best available provider.
        """
        provider = self.get_provider("data_extraction")

        if provider == "openai" and self.openai_extractor:
            return self.openai_extractor.extract_products_and_pricing(competitor_name, content)
        elif provider == "gemini" and self.gemini_extractor:
            # Gemini extractor doesn't have this method yet, use OpenAI if available
            if self.openai_extractor:
                return self.openai_extractor.extract_products_and_pricing(competitor_name, content)
            return {"products": [], "error": "Gemini doesn't support product extraction yet"}

        return {"products": [], "error": "No AI provider available"}


# Convenience function (updated for v5.0.2)
def extract_competitor_data(
    competitor_name: str,
    content: str,
    page_type: str = "homepage",
    use_hybrid: bool = True
) -> ExtractedData:
    """
    Extract competitor data from content.

    Args:
        competitor_name: Name of the competitor
        content: Page content to analyze
        page_type: Type of page (homepage, pricing, about, features, customers)
        use_hybrid: If True, uses hybrid AI routing (v5.0.2+)

    Returns:
        ExtractedData with extracted fields
    """
    if use_hybrid:
        extractor = HybridExtractor()
        if extractor.is_available:
            return extractor.extract_from_content(competitor_name, content, page_type)

    # Fallback to OpenAI-only
    extractor = GPTExtractor()
    return extractor.extract_from_content(competitor_name, content, page_type)


def get_extractor(provider: Optional[str] = None) -> Any:
    """
    Get the appropriate extractor based on configuration.

    Args:
        provider: Override provider ("openai", "gemini", or "hybrid")

    Returns:
        GPTExtractor, GeminiExtractor, or HybridExtractor
    """
    provider = provider or os.getenv("AI_PROVIDER", "hybrid")

    if provider == "hybrid":
        return HybridExtractor()
    elif provider == "gemini" and GEMINI_AVAILABLE and GeminiExtractor:
        return GeminiExtractor()
    else:
        return GPTExtractor()


# Test function
def test_extraction():
    """Test the extractor with sample content."""
    sample_content = """
    Phreesia - Patient Intake Solutions
    
    Pricing: Starting at $3 per patient visit
    
    Features:
    - Digital patient intake
    - Insurance eligibility verification
    - Patient payments and collections
    - Appointment reminders
    - Patient surveys
    
    Integrations: Epic, Cerner, Allscripts, athenahealth, eClinicalWorks
    
    Trusted by over 3,000 healthcare organizations
    
    HIPAA compliant, SOC 2 certified, HITRUST certified
    
    Founded in 2005, headquartered in Raleigh, NC
    """
    
    extractor = GPTExtractor()
    result = extractor.extract_from_content("Phreesia", sample_content, "homepage")
    
    print("Extraction Result:")
    for field, value in asdict(result).items():
        if value:
            print(f"  {field}: {value}")


if __name__ == "__main__":
    test_extraction()
