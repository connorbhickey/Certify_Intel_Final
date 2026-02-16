"""
Certify Intel - Data Population Script
Populates missing data fields for competitors using available data sources.
"""
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import SessionLocal, Competitor


# Known data for major competitors (fallback data)
KNOWN_COMPETITOR_DATA = {
    "phreesia": {
        "g2_rating": "4.3",
        "employee_count": "1800+",
        "customer_count": "3500+",
        "year_founded": "2005",
        "headquarters": "Wilmington, NC",
        "funding_total": "Public (NYSE: PHR)",
        "certifications": "HIPAA; HITRUST; SOC2"
    },
    "clearwave": {
        "g2_rating": "4.5",
        "employee_count": "200+",
        "customer_count": "1500+",
        "year_founded": "2004",
        "headquarters": "Atlanta, GA",
        "funding_total": "$50M+",
        "certifications": "HIPAA; SOC2"
    },
    "waystar": {
        "g2_rating": "4.1",
        "employee_count": "2000+",
        "customer_count": "450000+",
        "year_founded": "2017",
        "headquarters": "Louisville, KY",
        "funding_total": "Public",
        "certifications": "HIPAA; SOC2; HITRUST"
    },
    "cedar": {
        "g2_rating": "4.5",
        "employee_count": "500+",
        "customer_count": "55+",
        "year_founded": "2016",
        "headquarters": "New York, NY",
        "funding_total": "$350M+",
        "certifications": "HIPAA; SOC2"
    },
    "luma health": {
        "g2_rating": "4.6",
        "employee_count": "200+",
        "customer_count": "600+",
        "year_founded": "2015",
        "headquarters": "San Francisco, CA",
        "funding_total": "$160M+",
        "certifications": "HIPAA; SOC2"
    },
    "zocdoc": {
        "g2_rating": "4.2",
        "employee_count": "700+",
        "customer_count": "50000+",
        "year_founded": "2007",
        "headquarters": "New York, NY",
        "funding_total": "$376M+",
        "certifications": "HIPAA"
    },
    "athenahealth": {
        "g2_rating": "3.7",
        "employee_count": "7000+",
        "customer_count": "150000+",
        "year_founded": "1997",
        "headquarters": "Watertown, MA",
        "funding_total": "Private (PE: Hellman & Friedman)",
        "certifications": "HIPAA; HITRUST; SOC2"
    },
    "nextgen healthcare": {
        "g2_rating": "3.5",
        "employee_count": "2600+",
        "customer_count": "100000+",
        "year_founded": "1974",
        "headquarters": "Irvine, CA",
        "funding_total": "Public (NASDAQ: NXGN)",
        "certifications": "HIPAA; ONC"
    },
    "veradigm": {
        "g2_rating": "3.5",
        "employee_count": "4000+",
        "customer_count": "500000+ users",
        "year_founded": "2022",
        "headquarters": "Chicago, IL",
        "funding_total": "Public (Allscripts spinoff)",
        "certifications": "HIPAA; HITRUST"
    },
    "imprivata": {
        "g2_rating": "4.4",
        "employee_count": "800+",
        "customer_count": "2000+",
        "year_founded": "2002",
        "headquarters": "Waltham, MA",
        "funding_total": "PE Backed (Thoma Bravo)",
        "certifications": "HIPAA; EPCS"
    },
    "kyruus": {
        "g2_rating": "4.4",
        "employee_count": "500+",
        "customer_count": "700+",
        "year_founded": "2010",
        "headquarters": "Boston, MA",
        "funding_total": "$150M+",
        "certifications": "HIPAA; SOC2"
    },
}


def populate_missing_fields():
    """Populate missing data fields using known data."""
    db = SessionLocal()
    
    print("=" * 60)
    print("Certify Intel - Data Population")
    print("=" * 60)
    
    competitors = db.query(Competitor).filter(Competitor.is_deleted == False).all()
    print(f"Total competitors: {len(competitors)}")
    
    updated = 0
    
    for comp in competitors:
        name_lower = comp.name.lower()
        known_data = KNOWN_COMPETITOR_DATA.get(name_lower, {})
        
        changes = []
        
        # Update missing fields from known data
        if known_data:
            for field, value in known_data.items():
                current = getattr(comp, field, None)
                if not current or current == "Unknown":
                    setattr(comp, field, value)
                    changes.append(field)
        
        # Set default data quality score based on completeness
        completeness = calculate_completeness(comp)
        if comp.data_quality_score != int(completeness):
            comp.data_quality_score = int(completeness)
            changes.append("data_quality_score")
        
        # Update timestamp
        if changes:
            comp.last_updated = datetime.utcnow()
            updated += 1
            print(f"  ✅ {comp.name}: Updated {len(changes)} fields - {', '.join(changes[:3])}{'...' if len(changes) > 3 else ''}")
    
    db.commit()
    db.close()
    
    print("-" * 60)
    print(f"Updated {updated} competitors with missing data")
    print("=" * 60)
    
    return updated


def calculate_completeness(comp: Competitor) -> float:
    """Calculate data completeness score (0-100)."""
    fields = [
        "website", "status", "threat_level", "pricing_model", "base_price",
        "product_categories", "key_features", "integration_partners",
        "target_segments", "customer_count", "g2_rating", "employee_count",
        "year_founded", "headquarters", "funding_total"
    ]
    
    filled = 0
    for field in fields:
        value = getattr(comp, field, None)
        if value and value != "Unknown" and value != "N/A":
            filled += 1
    
    return round((filled / len(fields)) * 100, 1)


def show_data_quality_report():
    """Show data quality report for all competitors."""
    db = SessionLocal()
    competitors = db.query(Competitor).filter(Competitor.is_deleted == False).all()
    db.close()
    
    print("\n" + "=" * 60)
    print("DATA QUALITY REPORT")
    print("=" * 60)
    
    # Group by quality
    high_quality = [c for c in competitors if calculate_completeness(c) >= 80]
    medium_quality = [c for c in competitors if 50 <= calculate_completeness(c) < 80]
    low_quality = [c for c in competitors if calculate_completeness(c) < 50]
    
    print(f"\n🟢 High Quality (80%+): {len(high_quality)} competitors")
    print(f"🟡 Medium Quality (50-79%): {len(medium_quality)} competitors")
    print(f"🔴 Low Quality (<50%): {len(low_quality)} competitors")
    
    # Show lowest quality competitors
    if low_quality:
        print(f"\n⚠️  Competitors needing attention:")
        for comp in sorted(low_quality, key=lambda c: calculate_completeness(c))[:10]:
            score = calculate_completeness(comp)
            print(f"   - {comp.name}: {score}%")
    
    # Average quality
    avg_quality = sum(calculate_completeness(c) for c in competitors) / len(competitors)
    print(f"\n📊 Average Data Quality: {avg_quality:.1f}%")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Populate missing competitor data")
    parser.add_argument("--report", action="store_true", help="Show data quality report only")
    args = parser.parse_args()
    
    if args.report:
        show_data_quality_report()
    else:
        populate_missing_fields()
        show_data_quality_report()
