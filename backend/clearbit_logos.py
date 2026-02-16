"""
Clearbit Logo API Integration

Free API to fetch company logos by domain.
No API key required - just construct URL from company website.
"""


def get_logo_url(website: str) -> str:
    """
    Get Clearbit logo URL for a company website.
    
    Args:
        website: Company website URL (e.g., "https://phreesia.com")
        
    Returns:
        Clearbit logo URL (e.g., "https://logo.clearbit.com/phreesia.com")
    """
    if not website:
        return ""
    
    # Extract domain from website URL
    domain = website.replace('https://', '').replace('http://', '').replace('www.', '')
    domain = domain.split('/')[0]  # Remove path
    
    if not domain:
        return ""
    
    return f"https://logo.clearbit.com/{domain}"


def enrich_competitor_with_logo(competitor: dict) -> dict:
    """
    Add logo_url to a competitor dictionary.
    
    Args:
        competitor: Competitor dict with 'website' field
        
    Returns:
        Same dict with 'logo_url' field added
    """
    website = competitor.get('website', '')
    competitor['logo_url'] = get_logo_url(website)
    return competitor


def enrich_competitors_with_logos(competitors: list) -> list:
    """
    Add logo_url to all competitors in a list.
    
    Args:
        competitors: List of competitor dicts
        
    Returns:
        Same list with 'logo_url' fields added
    """
    return [enrich_competitor_with_logo(c) for c in competitors]
