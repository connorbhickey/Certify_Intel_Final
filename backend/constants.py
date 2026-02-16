"""
Certify Intel - Shared Constants

Centralizes version string, hallucination instruction, and other constants
used across multiple modules.
"""

__version__ = "8.3.1"

# =============================================================================
# NO-HALLUCINATION SYSTEM INSTRUCTION (v7.2.0)
# Appended to every AI prompt to prevent fabrication of data.
# =============================================================================
NO_HALLUCINATION_INSTRUCTION = (
    "\n\nCRITICAL DATA INTEGRITY RULE: You must ONLY reference data provided "
    "in this context. Do NOT fabricate, estimate, or assume any data points. "
    "If data is not available, state 'No verified data available for this metric.'"
)

# Known healthcare IT public companies with tickers
KNOWN_TICKERS = {
    # Healthcare IT
    "phreesia": {"symbol": "PHR", "exchange": "NYSE", "name": "Phreesia Inc"},
    "health catalyst": {"symbol": "HCAT", "exchange": "NASDAQ", "name": "Health Catalyst Inc"},
    "veeva": {"symbol": "VEEV", "exchange": "NYSE", "name": "Veeva Systems Inc"},
    "teladoc": {"symbol": "TDOC", "exchange": "NYSE", "name": "Teladoc Health Inc"},
    "doximity": {"symbol": "DOCS", "exchange": "NYSE", "name": "Doximity Inc"},
    "hims & hers": {"symbol": "HIMS", "exchange": "NYSE", "name": "Hims & Hers Health Inc"},
    "definitive healthcare": {"symbol": "DH", "exchange": "NASDAQ", "name": "Definitive Healthcare Corp"},
    "carecloud": {"symbol": "CCLD", "exchange": "NASDAQ", "name": "CareCloud Inc"},
    # Major Tech Companies
    "apple": {"symbol": "AAPL", "exchange": "NASDAQ", "name": "Apple Inc"},
    "microsoft": {"symbol": "MSFT", "exchange": "NASDAQ", "name": "Microsoft Corporation"},
    "google": {"symbol": "GOOGL", "exchange": "NASDAQ", "name": "Alphabet Inc"},
    "alphabet": {"symbol": "GOOGL", "exchange": "NASDAQ", "name": "Alphabet Inc"},
    "amazon": {"symbol": "AMZN", "exchange": "NASDAQ", "name": "Amazon.com Inc"},
    "meta": {"symbol": "META", "exchange": "NASDAQ", "name": "Meta Platforms Inc"},
    "facebook": {"symbol": "META", "exchange": "NASDAQ", "name": "Meta Platforms Inc"},
    "nvidia": {"symbol": "NVDA", "exchange": "NASDAQ", "name": "NVIDIA Corporation"},
    "tesla": {"symbol": "TSLA", "exchange": "NASDAQ", "name": "Tesla Inc"},
    "oracle": {"symbol": "ORCL", "exchange": "NYSE", "name": "Oracle Corporation"},
    "salesforce": {"symbol": "CRM", "exchange": "NYSE", "name": "Salesforce Inc"},
    "adobe": {"symbol": "ADBE", "exchange": "NASDAQ", "name": "Adobe Inc"},
    "ibm": {"symbol": "IBM", "exchange": "NYSE", "name": "International Business Machines"},
    "intel": {"symbol": "INTC", "exchange": "NASDAQ", "name": "Intel Corporation"},
    "cisco": {"symbol": "CSCO", "exchange": "NASDAQ", "name": "Cisco Systems Inc"},
    # Healthcare/Insurance
    "unitedhealth": {"symbol": "UNH", "exchange": "NYSE", "name": "UnitedHealth Group Inc"},
    "cvs health": {"symbol": "CVS", "exchange": "NYSE", "name": "CVS Health Corporation"},
    "cigna": {"symbol": "CI", "exchange": "NYSE", "name": "The Cigna Group"},
    "anthem": {"symbol": "ELV", "exchange": "NYSE", "name": "Elevance Health Inc"},
    "elevance": {"symbol": "ELV", "exchange": "NYSE", "name": "Elevance Health Inc"},
    "humana": {"symbol": "HUM", "exchange": "NYSE", "name": "Humana Inc"},
    "epic systems": {"symbol": None, "exchange": None, "name": "Epic Systems Corporation"},  # Private
    "cerner": {"symbol": "ORCL", "exchange": "NYSE", "name": "Cerner (Oracle Health)"},  # Acquired by Oracle
    "athenahealth": {"symbol": None, "exchange": None, "name": "athenahealth"},  # Private (PE owned)
}
