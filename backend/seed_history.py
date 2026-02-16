"""
Seed Historical Data
Generates 12 months of fake change history for active competitors to populate the "Timeline" and "Trends" charts.
Run: ALLOW_DEMO_SEED=true python seed_history.py
"""
import os
import sys
import random
from datetime import datetime, timedelta
from database import SessionLocal, Competitor, DataChangeHistory, engine, Base

if os.getenv('ALLOW_DEMO_SEED') != 'true':
    sys.exit("Demo seeding disabled in production. Set ALLOW_DEMO_SEED=true to run.")


def seed_history():
    print("Seeding historical data...")
    db = SessionLocal()
    
    # Get active competitors
    competitors = db.query(Competitor).filter(Competitor.status == "Active").all()
    
    
    if not competitors:
        print("No active competitors found. Seeding base competitors first...")
        initial_competitors = [
            Competitor(name="Phreesia", website="https://www.phreesia.com", status="Active", threat_level="High"),
            Competitor(name="Veeva", website="https://www.veeva.com", status="Active", threat_level="Low"),
            Competitor(name="Health Catalyst", website="https://www.healthcatalyst.com", status="Active", threat_level="Medium"),
            Competitor(name="Teladoc", website="https://www.teladochealth.com", status="Active", threat_level="Low")
        ]
        db.add_all(initial_competitors)
        db.commit()
        competitors = db.query(Competitor).filter(Competitor.status == "Active").all()


    change_types = [
        ("pricing_model", ["Subscription", "Per Provider", "Enterprise License", "Tiered"]),
        ("threat_level", ["Low", "Medium", "High"]),
        ("product_categories", ["Patient Intake", "Telehealth", "RCM", "Analytics"]),
        ("employee_count", ["150", "300", "500", "1200", "2500"]),
        ("funding_total", ["$10M", "$50M", "$120M", "$300M"]),
        ("recent_launches", ["AI Scribe", "Mobile App v2", "Payment Portal", "EHR Connect"])
    ]

    count = 0
    for comp in competitors:
        # Generate 5-15 events per competitor over the last year
        num_events = random.randint(5, 15)
        
        # Ensure employee growth rate is populated
        if not comp.employee_growth_rate:
            comp.employee_growth_rate = f"{random.randint(5, 40)}%"
            
        print(f"Generating {num_events} events for {comp.name}...")
        
        for _ in range(num_events):
            field, values = random.choice(change_types)
            old_val = random.choice(values)
            new_val = random.choice(values)
            
            while new_val == old_val:
                new_val = random.choice(values)
            
            # Random date in last 365 days
            days_ago = random.randint(1, 365)
            date = datetime.utcnow() - timedelta(days=days_ago)
            
            change = DataChangeHistory(
                competitor_id=comp.id,
                competitor_name=comp.name,
                field_name=field,
                old_value=old_val,
                new_value=new_val,
                changed_by="system_seed",
                change_reason="Historical data backfill",
                source_url="https://web.archive.org",
                changed_at=date
            )
            db.add(change)
            count += 1
            
    db.commit()
    print(f"Successfully added {count} historical records.")
    db.close()

if __name__ == "__main__":
    seed_history()
