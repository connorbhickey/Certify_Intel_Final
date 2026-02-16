"""
Seed demo data for Certify Intel presentation.
Run: ALLOW_DEMO_SEED=true python seed_demo_data.py
"""
import os
import sys

if os.getenv('ALLOW_DEMO_SEED') != 'true':
    sys.exit("Demo seeding disabled in production. Set ALLOW_DEMO_SEED=true to run.")

from database import SessionLocal, Competitor
from datetime import datetime

db = SessionLocal()

# Major healthcare IT competitors for patient intake/engagement
competitors = [
    {
        'name': 'Phreesia',
        'website': 'https://phreesia.com',
        'threat_level': 'HIGH',
        'notes': 'Leading patient intake management platform. Public company (NYSE: PHR). Offers mobile check-in, payments, and clinical data collection.',
        'pricing_model': 'Per Provider/Month',
        'base_price': '$399',
        'key_features': 'Mobile Check-in; Patient Payments; Eligibility Verification; Clinical Intake; Analytics Dashboard',
        'target_segments': 'Large Health Systems; Specialty Practices',
        'integration_partners': 'Epic; Cerner; Allscripts; athenahealth',
        'customer_count': '3,500+ healthcare organizations',
        'employee_count': '2,000+',
        'year_founded': '2005',
        'headquarters': 'Wilmington, DE',
        'is_public': True,
        'ticker_symbol': 'PHR',
        'stock_exchange': 'NYSE',
    },
    {
        'name': 'Clearwave',
        'website': 'https://clearwave.com',
        'threat_level': 'HIGH',
        'notes': 'Self-service patient check-in kiosks and digital intake. Strong in orthopedics and specialty practices.',
        'pricing_model': 'Per Location/Month',
        'base_price': '$599',
        'key_features': 'Kiosk Check-in; Mobile Intake; Eligibility; Patient Payments; Insurance Card Scanning',
        'target_segments': 'Orthopedics; Specialty Practices; Multi-location Groups',
        'integration_partners': 'Athena; eClinicalWorks; NextGen',
        'customer_count': '1,800+ practices',
        'employee_count': '200+',
        'year_founded': '2004',
        'headquarters': 'Atlanta, GA',
    },
    {
        'name': 'Relatient (Envera Health)',
        'website': 'https://relatient.com',
        'threat_level': 'MEDIUM',
        'notes': 'Patient engagement and communication platform. Acquired by Envera Health. Strong in appointment reminders.',
        'pricing_model': 'Per Provider/Month',
        'base_price': '$149',
        'key_features': 'Appointment Reminders; Two-way Texting; Patient Surveys; Broadcast Messaging',
        'target_segments': 'Small to Medium Practices',
        'integration_partners': 'Multiple EHR integrations',
        'customer_count': '50,000+ providers',
        'employee_count': '300+',
        'year_founded': '2014',
        'headquarters': 'Franklin, TN',
    },
    {
        'name': 'Solutionreach',
        'website': 'https://solutionreach.com',
        'threat_level': 'MEDIUM',
        'notes': 'Patient relationship management focused on dental and small practices. Strong in reviews management.',
        'pricing_model': 'Per Location/Month',
        'base_price': '$299',
        'key_features': 'Appointment Reminders; Online Scheduling; Reviews Management; Recall Campaigns',
        'target_segments': 'Dental; Small Medical Practices',
        'integration_partners': 'Dentrix; Eaglesoft; Open Dental',
        'customer_count': '30,000+ practices',
        'employee_count': '400+',
        'year_founded': '2000',
        'headquarters': 'Lehi, UT',
    },
    {
        'name': 'Luma Health',
        'website': 'https://lumahealth.io',
        'threat_level': 'HIGH',
        'notes': 'Patient success platform with AI-powered scheduling. Well-funded startup challenging established players.',
        'pricing_model': 'Per Provider/Month',
        'base_price': '$250',
        'key_features': 'Smart Scheduling; Waitlist Management; Patient Referrals; AI Chatbot; Analytics',
        'target_segments': 'Health Systems; Large Groups',
        'integration_partners': 'Epic; Cerner; athenahealth; Allscripts',
        'customer_count': '600+ health systems',
        'employee_count': '200+',
        'year_founded': '2015',
        'headquarters': 'San Francisco, CA',
    },
    {
        'name': 'Yosi Health',
        'website': 'https://yosi.health',
        'threat_level': 'MEDIUM',
        'notes': 'Virtual waiting room and digital intake. Growing in post-COVID market.',
        'pricing_model': 'Per Provider/Month',
        'base_price': '$199',
        'key_features': 'Virtual Waiting Room; Digital Intake; Telehealth Triage; Patient Queue',
        'target_segments': 'Urgent Care; Primary Care',
        'integration_partners': 'Multiple EHR systems',
        'customer_count': '1,000+ locations',
        'employee_count': '75+',
        'year_founded': '2016',
        'headquarters': 'New York, NY',
    },
    {
        'name': 'Experian Health',
        'website': 'https://experianhealth.com',
        'threat_level': 'HIGH',
        'notes': 'Enterprise revenue cycle and patient access. Part of Experian. Strong in eligibility verification.',
        'pricing_model': 'Per Transaction',
        'base_price': '$0.50',
        'key_features': 'Real-time Eligibility; Prior Authorization; Patient Estimates; Identity Verification',
        'target_segments': 'Large Health Systems; Revenue Cycle',
        'integration_partners': 'Epic; Cerner; All major EHRs',
        'customer_count': '60% of US hospitals',
        'employee_count': '1,500+',
        'year_founded': '1996',
        'headquarters': 'Franklin, TN',
        'is_public': True,
        'ticker_symbol': 'EXPN.L',
        'stock_exchange': 'LSE',
    },
    {
        'name': 'Kyruus',
        'website': 'https://kyruus.com',
        'threat_level': 'MEDIUM',
        'notes': 'Provider search and scheduling platform. Focused on patient access at health systems.',
        'pricing_model': 'Enterprise Contract',
        'base_price': 'Contact Sales',
        'key_features': 'Provider Search; Online Scheduling; Provider Data Management; Patient Matching',
        'target_segments': 'Large Health Systems',
        'integration_partners': 'Epic; Cerner',
        'customer_count': '500+ health systems',
        'employee_count': '300+',
        'year_founded': '2010',
        'headquarters': 'Boston, MA',
    },
    {
        'name': 'Tebra (Kareo + PatientPop)',
        'website': 'https://tebra.com',
        'threat_level': 'MEDIUM',
        'notes': 'Practice management and patient engagement for independent practices. Result of Kareo + PatientPop merger.',
        'pricing_model': 'Per Provider/Month',
        'base_price': '$149',
        'key_features': 'Practice Management; Patient Engagement; Online Presence; Billing; Telehealth',
        'target_segments': 'Independent Practices; Small Groups',
        'integration_partners': 'Integrated platform',
        'customer_count': '100,000+ providers',
        'employee_count': '700+',
        'year_founded': '2022',
        'headquarters': 'Costa Mesa, CA',
    },
    {
        'name': 'Rectangle Health',
        'website': 'https://rectanglehealth.com',
        'threat_level': 'LOW',
        'notes': 'Patient payment and financing platform. Strong in payment processing.',
        'pricing_model': 'Transaction Fee',
        'base_price': '2.5% + $0.25',
        'key_features': 'Patient Payments; Payment Plans; Digital Statements; Card-on-File',
        'target_segments': 'All Practice Sizes',
        'integration_partners': 'Multiple EHR/PM systems',
        'customer_count': '40,000+ practices',
        'employee_count': '500+',
        'year_founded': '1993',
        'headquarters': 'Valhalla, NY',
    },
]

print("Seeding demo competitor data...")
print("-" * 50)

added = 0
for comp_data in competitors:
    existing = db.query(Competitor).filter(Competitor.name == comp_data['name']).first()
    if not existing:
        comp = Competitor(**comp_data)
        db.add(comp)
        added += 1
        print(f"  Added: {comp_data['name']} ({comp_data['threat_level']})")
    else:
        print(f"  Exists: {comp_data['name']}")

db.commit()

print("-" * 50)
print(f"Total added: {added} competitors")
print(f"Database now has: {db.query(Competitor).count()} competitors")
db.close()

print("\nDemo data seeding complete!")
