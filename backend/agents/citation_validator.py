"""
Certify Intel v7.0 - Citation Validation System
================================================

Validates all citations in agent responses to prevent hallucination.

CRITICAL: This module is the last line of defense against AI hallucinations.
Every agent response passes through citation validation before being returned.

Validation Rules:
1. All [Source: X] citations must reference real documents in knowledge base
2. All competitor claims must reference competitors in database
3. Citations to external sources must have valid URLs
4. Fabricated sources are removed with warnings
5. Responses without sources for factual claims are flagged

Usage:
    from agents.citation_validator import CitationValidator

    validator = CitationValidator(kb_context, competitor_context)
    result = await validator.validate(response_text, citations)
"""

import re
import math
import logging
from collections import Counter
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of citation validation."""
    is_valid: bool
    valid_citations: List[Dict[str, Any]]
    invalid_citations: List[Dict[str, Any]]
    warnings: List[str]
    cleaned_response: str
    validation_time_ms: float


@dataclass
class CitationMatch:
    """A citation found in text."""
    full_match: str
    source_reference: str
    position: int
    is_valid: bool = False
    matched_source: Optional[Dict[str, Any]] = None


class CitationValidator:
    """
    Validates citations against known sources.

    Ensures no hallucinated citations make it to the user.
    """

    # Patterns for finding citations in text
    CITATION_PATTERNS = [
        r'\[Source:\s*([^\]]+)\]',           # [Source: Document Name]
        r'\[Source\s+(\d+)\]',                # [Source 1]
        r'\[(\d+)\]',                         # [1]
        r'\(Source:\s*([^\)]+)\)',            # (Source: Document Name)
        r'According to\s+([^,\.]+)',          # According to Document Name
        r'Per\s+([^,\.]+)',                   # Per Document Name
    ]

    def __init__(
        self,
        knowledge_base_context: List[Dict[str, Any]] = None,
        competitor_context: List[Dict[str, Any]] = None,
        external_sources: List[Dict[str, Any]] = None
    ):
        self.kb_context = knowledge_base_context or []
        self.competitor_context = competitor_context or []
        self.external_sources = external_sources or []

        # Build lookup tables
        self._build_lookups()

    def _build_lookups(self):
        """Build lookup tables for fast validation."""
        self.kb_lookup = {}
        for i, doc in enumerate(self.kb_context, 1):
            doc_id = doc.get("id", f"KB-{i}")
            self.kb_lookup[str(doc_id).lower()] = doc
            self.kb_lookup[f"kb-{i}".lower()] = doc
            self.kb_lookup[f"source {i}".lower()] = doc
            self.kb_lookup[f"source{i}".lower()] = doc
            self.kb_lookup[str(i)] = doc

        self.competitor_lookup = {}
        for comp in self.competitor_context:
            name = comp.get("name", "").lower()
            comp_id = str(comp.get("id", ""))
            if name:
                self.competitor_lookup[name] = comp
            if comp_id:
                self.competitor_lookup[comp_id] = comp

        self.external_lookup = {}
        for source in self.external_sources:
            url = source.get("url", "").lower()
            name = source.get("name", "").lower()
            if url:
                self.external_lookup[url] = source
            if name:
                self.external_lookup[name] = source

    def _check_semantic_similarity(
        self,
        claim_text: str,
        source_content: str,
        n: int = 3
    ) -> float:
        """
        Check semantic similarity between a claim and source content
        using character n-gram cosine similarity.

        Returns similarity score between 0.0 and 1.0.
        Citations with score < 0.3 are flagged as low_confidence.
        """
        if not claim_text or not source_content:
            return 0.0

        claim_lower = claim_text.lower().strip()
        source_lower = source_content.lower().strip()

        if len(claim_lower) < n or len(source_lower) < n:
            return 0.0

        # Generate character n-grams
        def get_ngrams(text: str, size: int) -> Counter:
            return Counter(text[i:i + size] for i in range(len(text) - size + 1))

        claim_ngrams = get_ngrams(claim_lower, n)
        source_ngrams = get_ngrams(source_lower, n)

        # Cosine similarity
        common_keys = set(claim_ngrams.keys()) & set(source_ngrams.keys())
        if not common_keys:
            return 0.0

        dot_product = sum(claim_ngrams[k] * source_ngrams[k] for k in common_keys)
        magnitude_a = math.sqrt(sum(v * v for v in claim_ngrams.values()))
        magnitude_b = math.sqrt(sum(v * v for v in source_ngrams.values()))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    async def validate(
        self,
        response_text: str,
        citations: List[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate all citations in response.

        Args:
            response_text: The agent's response text
            citations: List of structured citations (if provided separately)

        Returns:
            ValidationResult with valid/invalid citations and cleaned response
        """
        start_time = datetime.utcnow()

        # Find all citations in text
        text_citations = self._find_citations_in_text(response_text)

        # Combine with structured citations
        all_citations = list(citations or [])
        for tc in text_citations:
            all_citations.append({
                "source_id": tc.source_reference,
                "source_type": "text_reference",
                "match_text": tc.full_match,
                "position": tc.position
            })

        # Validate each citation
        valid_citations = []
        invalid_citations = []
        warnings = []

        for citation in all_citations:
            is_valid, matched_source, warning = self._validate_citation(citation)

            if is_valid:
                citation["matched_source"] = matched_source
                # Check semantic similarity if citation has content
                cited_content = citation.get("content", "")
                source_content = (matched_source or {}).get("content", "") or (matched_source or {}).get("notes", "")
                if cited_content and source_content:
                    similarity = self._check_semantic_similarity(cited_content, source_content)
                    citation["similarity_score"] = round(similarity, 3)
                    if similarity < 0.3:
                        citation["low_confidence"] = True
                        warnings.append(
                            f"Low semantic similarity ({similarity:.2f}) for citation "
                            f"'{citation.get('source_id', 'unknown')}' - may not accurately reflect source"
                        )
                valid_citations.append(citation)
            else:
                invalid_citations.append(citation)
                if warning:
                    warnings.append(warning)

        # Clean response if needed
        cleaned_response = response_text
        if invalid_citations:
            cleaned_response = self._clean_invalid_citations(
                response_text, invalid_citations
            )

        # Check for unsourced factual claims
        unsourced_warnings = self._check_unsourced_claims(response_text, valid_citations)
        warnings.extend(unsourced_warnings)

        validation_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return ValidationResult(
            is_valid=len(invalid_citations) == 0 and len(unsourced_warnings) == 0,
            valid_citations=valid_citations,
            invalid_citations=invalid_citations,
            warnings=warnings,
            cleaned_response=cleaned_response,
            validation_time_ms=validation_time
        )

    def _find_citations_in_text(self, text: str) -> List[CitationMatch]:
        """Find all citation patterns in text."""
        matches = []

        for pattern in self.CITATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(CitationMatch(
                    full_match=match.group(0),
                    source_reference=match.group(1),
                    position=match.start()
                ))

        return matches

    def _validate_citation(
        self,
        citation: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate a single citation.

        Returns:
            (is_valid, matched_source, warning_message)
        """
        source_id = str(citation.get("source_id", "")).lower().strip()

        if not source_id:
            return False, None, "Empty source reference"

        # Check knowledge base
        if source_id in self.kb_lookup:
            return True, self.kb_lookup[source_id], None

        # Check competitors
        if source_id in self.competitor_lookup:
            return True, self.competitor_lookup[source_id], None

        # Check common valid references
        valid_generic = [
            "competitor database",
            "knowledge base",
            "internal database",
            "discovery pipeline"
        ]
        if any(v in source_id for v in valid_generic):
            return True, {"type": "internal", "name": source_id}, None

        # Check if it's a competitor name (partial match)
        for comp_name, comp_data in self.competitor_lookup.items():
            if comp_name in source_id or source_id in comp_name:
                return True, comp_data, None

        # Check external sources
        if source_id in self.external_lookup:
            return True, self.external_lookup[source_id], None

        # Invalid citation
        return False, None, f"Citation '{source_id}' not found in valid sources"

    def _clean_invalid_citations(
        self,
        text: str,
        invalid_citations: List[Dict[str, Any]]
    ) -> str:
        """Remove invalid citations from response text."""
        cleaned = text

        for citation in invalid_citations:
            match_text = citation.get("match_text", "")
            if match_text and match_text in cleaned:
                # Remove the citation but keep surrounding text
                cleaned = cleaned.replace(match_text, "[citation removed]")

        return cleaned

    def _check_unsourced_claims(
        self,
        text: str,
        valid_citations: List[Dict[str, Any]]
    ) -> List[str]:
        """Check for factual claims without sources."""
        warnings = []

        # Patterns that indicate factual claims
        claim_patterns = [
            r'\b\d+%',                          # Percentages
            r'\$[\d,]+(?:\.\d{2})?[MBK]?',      # Dollar amounts
            r'\b(?:revenue|profit|market share)\b.*\d+',  # Financial claims
            r'\b(?:ranked|rated)\s+#?\d+',      # Rankings
            r'\b\d+(?:,\d{3})*\s+(?:employees|customers|users)',  # Counts
        ]

        for pattern in claim_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Check if there's a citation nearby (within 100 chars)
                match_pos = text.find(match)
                text_window = text[max(0, match_pos - 100):match_pos + len(match) + 100]

                has_citation = any(
                    c.get("match_text", "") in text_window
                    for c in valid_citations
                )

                if not has_citation:
                    warnings.append(
                        f"Potential unsourced claim: '{match}' - consider adding citation"
                    )

        return warnings[:5]  # Limit warnings

    def validate_citation_references_real_content(
        self,
        citation: Dict[str, Any],
        response_text: str
    ) -> bool:
        """
        Verify that a citation actually refers to content that exists.

        This is a deeper validation that checks if the cited content
        actually appears in the source document.
        """
        source_id = citation.get("source_id", "")
        quoted_content = citation.get("content", "")

        if not source_id or not quoted_content:
            return False

        # Find the source
        source = None
        if source_id.lower() in self.kb_lookup:
            source = self.kb_lookup[source_id.lower()]
        elif source_id.lower() in self.competitor_lookup:
            source = self.competitor_lookup[source_id.lower()]

        if not source:
            return False

        # Check if quoted content appears in source
        source_content = source.get("content", "") or source.get("notes", "")

        # Normalize for comparison
        normalized_quote = quoted_content.lower().strip()
        normalized_source = source_content.lower()

        # Check for substantial overlap
        words = normalized_quote.split()
        if len(words) < 5:
            return True  # Short quotes are hard to verify

        # At least 80% of words should appear in source
        matching_words = sum(1 for w in words if w in normalized_source)
        return matching_words / len(words) >= 0.8


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_citations_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract structured citations from response text.

    Useful for parsing agent responses that include inline citations.
    """
    validator = CitationValidator()
    matches = validator._find_citations_in_text(text)

    return [
        {
            "source_reference": m.source_reference,
            "full_match": m.full_match,
            "position": m.position
        }
        for m in matches
    ]


async def validate_agent_response(
    response_text: str,
    citations: List[Dict[str, Any]],
    kb_context: List[Dict[str, Any]] = None,
    competitor_context: List[Dict[str, Any]] = None
) -> ValidationResult:
    """
    Convenience function to validate an agent response.

    Usage:
        result = await validate_agent_response(
            response_text=agent_output,
            citations=agent_citations,
            kb_context=knowledge_base_docs,
            competitor_context=competitor_data
        )

        if not result.is_valid:
            logger.warning(f"Invalid citations: {result.invalid_citations}")
            response_text = result.cleaned_response
    """
    validator = CitationValidator(
        knowledge_base_context=kb_context,
        competitor_context=competitor_context
    )

    return await validator.validate(response_text, citations)


# CLI testing
if __name__ == "__main__":
    import asyncio

    async def test():
        # Test data
        kb_context = [
            {"id": "doc1", "content": "Epic Systems has 28% market share in EHR."},
            {"id": "doc2", "content": "Athenahealth revenue was $1.2B in 2024."}
        ]

        competitor_context = [
            {"id": 1, "name": "Epic Systems", "description": "Leading EHR vendor"},
            {"id": 2, "name": "Athenahealth", "description": "Cloud-based healthcare IT"}
        ]

        # Test response with valid and invalid citations
        response = """
        ## Competitive Analysis

        According to [Source: doc1], Epic Systems has 28% market share.
        This makes them [Source: Epic Systems] the market leader.

        However, [Source: Made Up Document] shows different data.
        We also see that [Source: doc2] confirms Athenahealth's revenue.

        The market is growing at 15% annually.
        """

        validator = CitationValidator(kb_context, competitor_context)
        result = await validator.validate(response)

        print("=== Citation Validation Test ===")
        print(f"Is Valid: {result.is_valid}")
        print(f"Valid Citations: {len(result.valid_citations)}")
        print(f"Invalid Citations: {len(result.invalid_citations)}")
        print(f"Warnings: {result.warnings}")
        print(f"Validation Time: {result.validation_time_ms:.2f}ms")

        if result.invalid_citations:
            print("\nInvalid citations removed:")
            for ic in result.invalid_citations:
                print(f"  - {ic.get('source_id')}")

    asyncio.run(test())
