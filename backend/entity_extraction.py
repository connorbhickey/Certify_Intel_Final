"""
Entity Extraction Engine for Certify Intel v7.1

Extracts structured data from Knowledge Base documents using GPT-4.
Links extracted entities to competitor records and creates KB extractions.

Key Features:
- GPT-4 powered entity recognition
- Competitor name fuzzy matching
- Product/service extraction
- Quantitative data extraction (pricing, metrics)
- Automatic entity linking with confidence scores
"""

import json
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """Represents an extracted entity from a document."""
    entity_type: str  # competitor, product, metric, date, location
    name: str
    value: Optional[str] = None
    context: str = ""  # Surrounding text
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedMetric:
    """Represents an extracted quantitative metric."""
    field_name: str  # customer_count, revenue, employee_count, etc.
    value: str
    unit: Optional[str] = None
    date_reference: Optional[str] = None  # "Q3 2025", "as of January 2026"
    competitor_name: Optional[str] = None
    context: str = ""
    confidence: float = 0.0


@dataclass
class ExtractionResult:
    """Result of entity extraction from a document."""
    document_id: str
    competitors_found: List[ExtractedEntity]
    products_found: List[ExtractedEntity]
    metrics_found: List[ExtractedMetric]
    dates_found: List[ExtractedEntity]
    extraction_confidence: float
    raw_extraction: Dict[str, Any]
    processing_time_ms: int


class EntityExtractionEngine:
    """
    Engine for extracting structured entities from document text.

    Uses GPT-4 to identify:
    - Company/competitor names
    - Products and services
    - Quantitative metrics (customer counts, revenue, pricing)
    - Dates and temporal references
    - Locations and regions
    """

    # Common competitor fields to extract
    METRIC_FIELDS = [
        "customer_count",
        "employee_count",
        "annual_revenue",
        "total_funding",
        "market_share",
        "pricing",
        "base_price",
        "contract_value",
        "growth_rate",
        "nps_score",
        "churn_rate",
        "win_rate"
    ]

    # Extraction prompt template
    EXTRACTION_PROMPT = """Analyze this document and extract structured competitive intelligence data.

DOCUMENT CONTENT:
{content}

EXTRACTION INSTRUCTIONS:
Extract the following information in JSON format:

1. **competitors**: List of companies mentioned
   - name: Company name
   - role: "competitor", "partner", "customer", or "vendor"
   - context: Brief quote where mentioned

2. **products**: Products or services mentioned
   - name: Product/service name
   - company: Company that offers it
   - category: Product category if identifiable
   - context: Brief description or quote

3. **metrics**: Quantitative data points
   - field_name: One of [customer_count, employee_count, annual_revenue, total_funding, market_share, pricing, base_price, growth_rate, nps_score]
   - value: The numeric value (with units if applicable)
   - company: Which company this metric is for
   - date_reference: When this data was valid (e.g., "Q3 2025", "as of 2026")
   - context: Surrounding sentence

4. **dates**: Important dates mentioned
   - date: The date or time period
   - event: What happened on this date
   - company: Related company if any

Return ONLY valid JSON in this exact format:
{{
    "competitors": [...],
    "products": [...],
    "metrics": [...],
    "dates": [...],
    "document_summary": "1-2 sentence summary of document content",
    "confidence": 0.0-1.0 (your confidence in the extraction quality)
}}

Focus on healthcare technology and competitive intelligence relevance.
If a field has no matches, return an empty array [].
"""

    def __init__(
        self,
        ai_router=None,
        db_session=None,
        openai_client=None
    ):
        """
        Initialize the extraction engine.

        Args:
            ai_router: AIRouter instance for model selection
            db_session: SQLAlchemy database session
            openai_client: OpenAI client for GPT-4 extraction
        """
        self.ai_router = ai_router
        self.db = db_session
        self.openai_client = openai_client

    async def extract_from_document(
        self,
        document_id: str,
        content: str,
        existing_competitors: Optional[List[Dict]] = None
    ) -> ExtractionResult:
        """
        Extract entities from document content.

        Args:
            document_id: ID of the source document
            content: Text content to analyze
            existing_competitors: List of known competitors for matching

        Returns:
            ExtractionResult with extracted entities
        """
        import time
        start_time = time.time()

        # Truncate content if too long (GPT-4 context limit)
        max_chars = 12000
        truncated_content = content[:max_chars]
        if len(content) > max_chars:
            truncated_content += "\n\n[Content truncated...]"

        # Build prompt
        prompt = self.EXTRACTION_PROMPT.format(content=truncated_content)

        # Call GPT-4 for extraction
        try:
            raw_extraction = await self._call_extraction_api(prompt)
        except Exception as e:
            logger.error(f"Extraction API call failed: {e}")
            raw_extraction = {
                "competitors": [],
                "products": [],
                "metrics": [],
                "dates": [],
                "document_summary": "",
                "confidence": 0.0
            }

        # Parse extraction results
        competitors_found = []
        for comp in raw_extraction.get("competitors", []):
            entity = ExtractedEntity(
                entity_type="competitor",
                name=comp.get("name", ""),
                context=comp.get("context", ""),
                confidence=0.8,  # Base confidence for GPT extraction
                metadata={"role": comp.get("role", "competitor")}
            )
            competitors_found.append(entity)

        products_found = []
        for prod in raw_extraction.get("products", []):
            entity = ExtractedEntity(
                entity_type="product",
                name=prod.get("name", ""),
                context=prod.get("context", ""),
                confidence=0.75,
                metadata={
                    "company": prod.get("company", ""),
                    "category": prod.get("category", "")
                }
            )
            products_found.append(entity)

        metrics_found = []
        for metric in raw_extraction.get("metrics", []):
            extracted_metric = ExtractedMetric(
                field_name=metric.get("field_name", "unknown"),
                value=str(metric.get("value", "")),
                unit=metric.get("unit"),
                date_reference=metric.get("date_reference"),
                competitor_name=metric.get("company"),
                context=metric.get("context", ""),
                confidence=0.7
            )
            metrics_found.append(extracted_metric)

        dates_found = []
        for date_info in raw_extraction.get("dates", []):
            entity = ExtractedEntity(
                entity_type="date",
                name=date_info.get("date", ""),
                context=date_info.get("event", ""),
                confidence=0.85,
                metadata={"company": date_info.get("company", "")}
            )
            dates_found.append(entity)

        processing_time = int((time.time() - start_time) * 1000)

        return ExtractionResult(
            document_id=document_id,
            competitors_found=competitors_found,
            products_found=products_found,
            metrics_found=metrics_found,
            dates_found=dates_found,
            extraction_confidence=raw_extraction.get("confidence", 0.5),
            raw_extraction=raw_extraction,
            processing_time_ms=processing_time
        )

    async def link_entities_to_competitors(
        self,
        extraction_result: ExtractionResult,
        known_competitors: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Link extracted entities to known competitor records.

        Uses fuzzy matching to find the best competitor match for each
        extracted company name.

        Args:
            extraction_result: Result from extract_from_document
            known_competitors: List of competitor records from database

        Returns:
            List of entity links with confidence scores
        """
        links = []

        # Build lookup for known competitors
        competitor_lookup = {}
        for comp in known_competitors:
            name = comp.get("name", "").lower()
            competitor_lookup[name] = comp

            # Also add common variations
            # e.g., "Epic Systems" -> "epic", "epic systems"
            words = name.split()
            if len(words) > 1:
                competitor_lookup[words[0]] = comp

        # Match extracted competitors
        for entity in extraction_result.competitors_found:
            match, confidence = self._fuzzy_match_competitor(
                entity.name,
                competitor_lookup
            )

            if match:
                links.append({
                    "document_id": extraction_result.document_id,
                    "competitor_id": match.get("id"),
                    "competitor_name": match.get("name"),
                    "extracted_name": entity.name,
                    "link_type": "inferred" if confidence < 0.95 else "explicit",
                    "link_confidence": confidence,
                    "entity_type": "competitor",
                    "context": entity.context
                })

        # Match competitors mentioned in metrics
        for metric in extraction_result.metrics_found:
            if metric.competitor_name:
                match, confidence = self._fuzzy_match_competitor(
                    metric.competitor_name,
                    competitor_lookup
                )

                if match:
                    links.append({
                        "document_id": extraction_result.document_id,
                        "competitor_id": match.get("id"),
                        "competitor_name": match.get("name"),
                        "extracted_name": metric.competitor_name,
                        "link_type": "inferred",
                        "link_confidence": confidence * metric.confidence,
                        "entity_type": "metric",
                        "field_name": metric.field_name,
                        "extracted_value": metric.value,
                        "context": metric.context
                    })

        return links

    async def save_extractions_to_db(
        self,
        document_id: str,
        kb_item_id: Optional[int],
        extraction_result: ExtractionResult,
        entity_links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Save extraction results to database.

        Creates:
        - KBEntityLink records for competitor links
        - KBDataExtraction records for metrics

        Args:
            document_id: ID of the source document
            kb_item_id: ID in knowledge_base table (if applicable)
            extraction_result: Result from extract_from_document
            entity_links: Result from link_entities_to_competitors

        Returns:
            Summary of saved records
        """
        if not self.db:
            return {"error": "No database session"}

        try:
            from database import KBEntityLink, KBDataExtraction

            links_created = 0
            extractions_created = 0

            # Group links by competitor to avoid duplicates
            competitor_links = {}
            for link in entity_links:
                comp_id = link.get("competitor_id")
                if comp_id and comp_id not in competitor_links:
                    competitor_links[comp_id] = link

            # Create entity links
            for comp_id, link in competitor_links.items():
                db_link = KBEntityLink(
                    document_id=document_id,
                    kb_item_id=kb_item_id,
                    competitor_id=comp_id,
                    link_type=link.get("link_type", "inferred"),
                    link_confidence=link.get("link_confidence", 0.0),
                    extracted_entities=json.dumps({
                        "name": link.get("extracted_name"),
                        "context": link.get("context")
                    })
                )
                self.db.add(db_link)
                links_created += 1

            # Create data extractions for metrics
            for link in entity_links:
                if link.get("entity_type") == "metric" and link.get("field_name"):
                    extraction = KBDataExtraction(
                        document_id=document_id,
                        kb_item_id=kb_item_id,
                        competitor_id=link.get("competitor_id"),
                        field_name=link.get("field_name"),
                        extracted_value=link.get("extracted_value", ""),
                        extraction_context=link.get("context", ""),
                        extraction_confidence=link.get("link_confidence", 0.0),
                        extraction_method="gpt_extraction",
                        status="pending"
                    )
                    self.db.add(extraction)
                    extractions_created += 1

            self.db.commit()

            return {
                "success": True,
                "links_created": links_created,
                "extractions_created": extractions_created,
                "document_id": document_id
            }

        except Exception as e:
            logger.error(f"Failed to save extractions: {e}")
            self.db.rollback()
            return {"error": str(e)}

    async def _call_extraction_api(self, prompt: str) -> Dict[str, Any]:
        """
        Call GPT-4 API for extraction.

        Falls back to regex-based extraction if API unavailable.
        """
        # Try OpenAI client first
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a competitive intelligence analyst. Extract structured data from documents. Always respond with valid JSON only."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=2000
                )

                content = response.choices[0].message.content
                # Parse JSON from response
                return self._parse_json_response(content)

            except Exception as e:
                logger.warning(f"OpenAI extraction failed: {e}")

        # Try AI router
        if self.ai_router:
            try:
                response = await self.ai_router.generate(
                    prompt=prompt,
                    task_type="extraction",
                    temperature=0.1
                )
                return self._parse_json_response(response.get("text", "{}"))
            except Exception as e:
                logger.warning(f"AI router extraction failed: {e}")

        # Fallback to basic regex extraction
        return self._regex_fallback_extraction(prompt)

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from API response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}")
            return {
                "competitors": [],
                "products": [],
                "metrics": [],
                "dates": [],
                "confidence": 0.0
            }

    def _regex_fallback_extraction(self, content: str) -> Dict[str, Any]:
        """
        Fallback extraction using regex patterns.

        Used when API is unavailable.
        """
        # Extract potential company names (capitalized words followed by Inc, Corp, etc.)
        company_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Inc|Corp|LLC|Ltd|Healthcare|Health|Medical|Systems|Technologies|Software))?)[\s,.]'
        companies = list(set(re.findall(company_pattern, content)))

        # Extract numbers with context
        metric_pattern = r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(customers?|employees?|users?|million|billion|%|\$|revenue)'
        metrics = re.findall(metric_pattern, content, re.IGNORECASE)

        # Extract years
        year_pattern = r'\b(20\d{2}|Q[1-4]\s+20\d{2}|January|February|March|April|May|June|July|August|September|October|November|December\s+20\d{2})\b'
        dates = list(set(re.findall(year_pattern, content)))

        return {
            "competitors": [{"name": c, "role": "unknown", "context": ""} for c in companies[:10]],
            "products": [],
            "metrics": [
                {
                    "field_name": self._guess_field_name(m[1]),
                    "value": m[0],
                    "company": None,
                    "context": ""
                }
                for m in metrics[:20]
            ],
            "dates": [{"date": d, "event": "", "company": ""} for d in dates[:10]],
            "confidence": 0.3  # Low confidence for regex extraction
        }

    def _guess_field_name(self, unit: str) -> str:
        """Guess field name from unit/context."""
        unit_lower = unit.lower()
        if "customer" in unit_lower or "user" in unit_lower:
            return "customer_count"
        elif "employee" in unit_lower:
            return "employee_count"
        elif "million" in unit_lower or "billion" in unit_lower or "$" in unit_lower or "revenue" in unit_lower:
            return "annual_revenue"
        elif "%" in unit_lower:
            return "growth_rate"
        return "unknown"

    def _fuzzy_match_competitor(
        self,
        extracted_name: str,
        competitor_lookup: Dict[str, Dict]
    ) -> Tuple[Optional[Dict], float]:
        """
        Fuzzy match extracted name to known competitors.

        Returns:
            Tuple of (matched_competitor, confidence)
        """
        if not extracted_name:
            return None, 0.0

        name_lower = extracted_name.lower().strip()

        # Exact match
        if name_lower in competitor_lookup:
            return competitor_lookup[name_lower], 1.0

        # Check each known competitor
        best_match = None
        best_score = 0.0

        for known_name, comp in competitor_lookup.items():
            score = self._name_similarity(name_lower, known_name)
            if score > best_score:
                best_score = score
                best_match = comp

        # Only return if above threshold
        if best_score >= 0.7:
            return best_match, best_score

        return None, 0.0

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two company names."""
        # Simple word-based similarity
        words1 = set(name1.lower().split())
        words2 = set(name2.lower().split())

        # Remove common words
        stop_words = {"inc", "corp", "llc", "ltd", "healthcare", "health", "medical", "systems", "technologies", "software", "the", "and"}
        words1 = words1 - stop_words
        words2 = words2 - stop_words

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0


# Convenience function for quick extraction
async def extract_and_link_entities(
    document_id: str,
    content: str,
    db_session,
    kb_item_id: Optional[int] = None,
    openai_client=None
) -> Dict[str, Any]:
    """
    Convenience function to extract entities and link to competitors.

    Args:
        document_id: ID of the source document
        content: Document text content
        db_session: SQLAlchemy database session
        kb_item_id: Optional ID in knowledge_base table
        openai_client: Optional OpenAI client

    Returns:
        Summary of extraction and linking results
    """
    from database import Competitor

    # Get known competitors
    competitors = db_session.query(Competitor).filter(
        Competitor.is_deleted == False
    ).all()

    known_competitors = [
        {"id": c.id, "name": c.name, "website": c.website}
        for c in competitors
    ]

    # Create engine and extract
    engine = EntityExtractionEngine(
        db_session=db_session,
        openai_client=openai_client
    )

    extraction_result = await engine.extract_from_document(
        document_id=document_id,
        content=content,
        existing_competitors=known_competitors
    )

    # Link entities
    entity_links = await engine.link_entities_to_competitors(
        extraction_result=extraction_result,
        known_competitors=known_competitors
    )

    # Save to database
    save_result = await engine.save_extractions_to_db(
        document_id=document_id,
        kb_item_id=kb_item_id,
        extraction_result=extraction_result,
        entity_links=entity_links
    )

    return {
        "extraction": {
            "competitors_found": len(extraction_result.competitors_found),
            "products_found": len(extraction_result.products_found),
            "metrics_found": len(extraction_result.metrics_found),
            "dates_found": len(extraction_result.dates_found),
            "confidence": extraction_result.extraction_confidence,
            "processing_time_ms": extraction_result.processing_time_ms
        },
        "linking": {
            "total_links": len(entity_links),
            "competitor_links": len([l for l in entity_links if l.get("entity_type") == "competitor"]),
            "metric_extractions": len([l for l in entity_links if l.get("entity_type") == "metric"])
        },
        "saved": save_result
    }
