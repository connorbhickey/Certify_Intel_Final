"""
Certify Intel - Comprehensive Data Population Script (v5.1.0)

Populates product data and news for ALL competitors.
This script should be run once to fill the database with initial data.

Features:
1. Extracts products from existing competitor data (product_categories, key_features)
2. Uses AI to discover products from competitor websites
3. Refreshes news for all competitors
4. Tracks progress and handles errors gracefully
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Competitor, CompetitorProduct, DataSource, NewsArticleCache


# ==============================================================================
# PRODUCT POPULATION
# ==============================================================================

def extract_products_from_existing_data(db) -> Dict[str, int]:
    """
    Extract products from existing product_categories and key_features fields.
    This creates CompetitorProduct records from data we already have.
    """
    print("\n" + "="*60)
    print("PHASE 1: Extract Products from Existing Data")
    print("="*60)

    stats = {"processed": 0, "products_created": 0, "skipped": 0}

    competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False
    ).all()

    for comp in competitors:
        stats["processed"] += 1

        # Skip if already has products
        existing_count = db.query(CompetitorProduct).filter(
            CompetitorProduct.competitor_id == comp.id
        ).count()

        if existing_count > 0:
            stats["skipped"] += 1
            continue

        products_to_create = []

        # Parse product_categories
        if comp.product_categories:
            categories = [c.strip() for c in comp.product_categories.replace(";", ",").split(",")]
            for cat in categories:
                if cat and len(cat) > 2:
                    # Create product from category
                    product_name = f"{comp.name} {cat}"
                    products_to_create.append({
                        "name": product_name,
                        "category": _categorize_product(cat),
                        "source": "product_categories"
                    })

        # Parse key_features to identify product types
        if comp.key_features:
            features = comp.key_features.lower()

            # Map features to product categories
            feature_product_map = {
                "intake": "Patient Intake",
                "check-in": "Patient Intake",
                "check in": "Patient Intake",
                "registration": "Patient Intake",
                "ehr": "EHR/EMR",
                "emr": "EHR/EMR",
                "electronic health": "EHR/EMR",
                "billing": "RCM/Billing",
                "rcm": "RCM/Billing",
                "revenue cycle": "RCM/Billing",
                "claims": "RCM/Billing",
                "payment": "Payments",
                "scheduling": "Practice Management",
                "practice management": "Practice Management",
                "pm": "Practice Management",
                "telehealth": "Telehealth",
                "telemedicine": "Telehealth",
                "patient engagement": "Patient Engagement",
                "reminders": "Patient Engagement",
                "portal": "Patient Portal",
                "analytics": "Analytics",
                "reporting": "Analytics",
                "eligibility": "Eligibility Verification",
                "verification": "Eligibility Verification",
            }

            for keyword, category in feature_product_map.items():
                if keyword in features:
                    # Check if we already have this category
                    existing = [p for p in products_to_create if p["category"] == category]
                    if not existing:
                        products_to_create.append({
                            "name": f"{comp.name} {category}",
                            "category": category,
                            "source": "key_features"
                        })

        # Also check boolean flags
        flag_product_map = {
            "has_pxp": ("Patient Experience Platform", "Patient Experience"),
            "has_rcm": ("Revenue Cycle Management", "RCM/Billing"),
            "has_payments": ("Patient Payments", "Payments"),
            "has_patient_mgmt": ("Patient Management", "Patient Management"),
            "has_pms": ("Practice Management System", "Practice Management"),
            "has_biometric": ("Biometric Authentication", "Identity"),
            "has_interoperability": ("Interoperability Platform", "Integration"),
        }

        for flag, (product_suffix, category) in flag_product_map.items():
            if getattr(comp, flag, False):
                existing = [p for p in products_to_create if p["category"] == category]
                if not existing:
                    products_to_create.append({
                        "name": f"{comp.name} {product_suffix}",
                        "category": category,
                        "source": f"boolean_flag:{flag}"
                    })

        # Create products
        for i, p in enumerate(products_to_create):
            try:
                product = CompetitorProduct(
                    competitor_id=comp.id,
                    product_name=p["name"],
                    product_category=p["category"],
                    is_primary_product=(i == 0),  # First one is primary
                    created_at=datetime.utcnow(),
                    last_updated=datetime.utcnow()
                )
                db.add(product)

                # Create DataSource record
                source = DataSource(
                    competitor_id=comp.id,
                    field_name=f"product:{p['name']}",
                    current_value=p["name"],
                    source_type="data_extraction",
                    source_name=f"Extracted from {p['source']}",
                    extraction_method="populate_script",
                    confidence_score=70,
                    confidence_level="moderate",
                    is_verified=False,
                    created_at=datetime.utcnow()
                )
                db.add(source)

                stats["products_created"] += 1

            except Exception as e:
                print(f"  Error creating product for {comp.name}: {e}")

        if products_to_create:
            print(f"  {comp.name}: {len(products_to_create)} products")

    db.commit()

    print(f"\nPhase 1 Complete:")
    print(f"  Competitors processed: {stats['processed']}")
    print(f"  Products created: {stats['products_created']}")
    print(f"  Skipped (already had products): {stats['skipped']}")

    return stats


def _categorize_product(text: str) -> str:
    """Categorize a product based on text."""
    text_lower = text.lower()

    categories = {
        "Patient Intake": ["intake", "check-in", "registration", "forms"],
        "Practice Management": ["pm", "practice", "scheduling", "appointment"],
        "EHR/EMR": ["ehr", "emr", "electronic health", "medical record"],
        "RCM/Billing": ["rcm", "billing", "revenue", "claims", "collection"],
        "Patient Engagement": ["engagement", "communication", "reminders", "recall"],
        "Telehealth": ["telehealth", "telemedicine", "virtual", "video"],
        "Payments": ["payment", "pay", "merchant"],
        "Eligibility Verification": ["eligibility", "verification", "insurance"],
        "Analytics": ["analytics", "reporting", "dashboard", "bi"],
        "Integration": ["integration", "interoperability", "api", "hl7", "fhir"],
    }

    for category, keywords in categories.items():
        for kw in keywords:
            if kw in text_lower:
                return category

    return "Other"


async def discover_products_with_ai(db) -> Dict[str, int]:
    """
    Use AI-powered product discovery for competitors still missing products.
    """
    print("\n" + "="*60)
    print("PHASE 2: AI-Powered Product Discovery")
    print("="*60)

    stats = {"processed": 0, "products_created": 0, "errors": 0}

    # Get competitors without products
    competitors_with_products = db.query(CompetitorProduct.competitor_id).distinct()
    competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False,
        Competitor.website.isnot(None),
        ~Competitor.id.in_(competitors_with_products)
    ).all()

    print(f"Competitors needing AI discovery: {len(competitors)}")

    if not competitors:
        print("All competitors have products!")
        return stats

    try:
        from product_discovery_crawler import ProductDiscoveryCrawler
    except ImportError:
        print("Product discovery crawler not available")
        return stats

    async with ProductDiscoveryCrawler(use_ai=True, headless=True) as crawler:
        for i, comp in enumerate(competitors[:50]):  # Limit to 50 for speed
            stats["processed"] += 1
            print(f"  [{i+1}/{min(len(competitors), 50)}] {comp.name}...", end=" ", flush=True)

            try:
                result = await crawler.discover_products(
                    comp.name,
                    comp.website,
                    comp.id
                )

                for product in result.products_found:
                    # Check if already exists
                    existing = db.query(CompetitorProduct).filter(
                        CompetitorProduct.competitor_id == comp.id,
                        CompetitorProduct.product_name.ilike(product.product_name)
                    ).first()

                    if not existing:
                        new_product = CompetitorProduct(
                            competitor_id=comp.id,
                            product_name=product.product_name,
                            product_category=product.product_category,
                            description=product.description,
                            target_segment=product.target_segment,
                            is_primary_product=product.is_primary_product,
                            created_at=datetime.utcnow(),
                            last_updated=datetime.utcnow()
                        )
                        db.add(new_product)
                        stats["products_created"] += 1

                if result.products_found:
                    print(f"{len(result.products_found)} products")
                    # Update competitor's product_categories
                    categories = list(set(p.product_category for p in result.products_found))
                    comp.product_categories = "; ".join(categories)
                else:
                    print("no products found")

                db.commit()

            except Exception as e:
                print(f"error: {str(e)[:50]}")
                stats["errors"] += 1
                db.rollback()

            # Rate limiting
            await asyncio.sleep(2)

    print(f"\nPhase 2 Complete:")
    print(f"  Competitors processed: {stats['processed']}")
    print(f"  Products created: {stats['products_created']}")
    print(f"  Errors: {stats['errors']}")

    return stats


# ==============================================================================
# NEWS POPULATION
# ==============================================================================

def populate_news_cache(db) -> Dict[str, int]:
    """
    Populate the news cache for all competitors.
    """
    print("\n" + "="*60)
    print("PHASE 3: News Cache Population")
    print("="*60)

    stats = {"competitors_processed": 0, "articles_cached": 0, "errors": 0}

    try:
        from comprehensive_news_scraper import ComprehensiveNewsScraper
        scraper = ComprehensiveNewsScraper()
    except ImportError:
        print("Comprehensive news scraper not available, using basic news monitor")
        try:
            from news_monitor import NewsMonitor
            scraper = None
            monitor = NewsMonitor()
        except ImportError:
            print("No news scraper available!")
            return stats

    competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False
    ).all()

    print(f"Processing news for {len(competitors)} competitors...")

    for i, comp in enumerate(competitors):
        stats["competitors_processed"] += 1

        # Skip if recently fetched
        recent = db.query(NewsArticleCache).filter(
            NewsArticleCache.competitor_id == comp.id,
            NewsArticleCache.fetched_at > datetime.utcnow() - timedelta(hours=6)
        ).first()

        if recent:
            continue

        print(f"  [{i+1}/{len(competitors)}] {comp.name}...", end=" ", flush=True)

        try:
            if scraper:
                articles = scraper.fetch_competitor_news(
                    competitor_name=comp.name,
                    competitor_id=comp.id,
                    days=30,
                    max_articles=30
                )
            else:
                digest = monitor.fetch_news(comp.name, days=30)
                articles = [
                    {
                        "title": a.title,
                        "url": a.url,
                        "source": a.source,
                        "source_type": "news_monitor",
                        "published_at": a.published_date,
                        "snippet": a.snippet,
                        "sentiment": a.sentiment,
                        "event_type": a.event_type,
                        "is_major_event": a.is_major_event
                    }
                    for a in digest.articles
                ]

            articles_added = 0
            for article in articles:
                # Check if already cached
                existing = db.query(NewsArticleCache).filter(
                    NewsArticleCache.url == article.get("url", "")
                ).first()

                if not existing and article.get("url"):
                    try:
                        # Parse date
                        pub_date = _parse_date(article.get("published_at"))

                        cache_entry = NewsArticleCache(
                            competitor_id=comp.id,
                            competitor_name=comp.name,
                            title=article.get("title", "")[:500],
                            url=article.get("url", ""),
                            source=article.get("source", "Unknown"),
                            source_type=article.get("source_type", "unknown"),
                            published_at=pub_date,
                            snippet=article.get("snippet", "")[:1000] if article.get("snippet") else None,
                            sentiment=article.get("sentiment", "neutral"),
                            event_type=article.get("event_type"),
                            is_major_event=article.get("is_major_event", False),
                            fetched_at=datetime.utcnow(),
                            cache_expires_at=datetime.utcnow() + timedelta(hours=24),
                            created_at=datetime.utcnow()
                        )
                        db.add(cache_entry)
                        articles_added += 1
                        stats["articles_cached"] += 1
                    except Exception as e:
                        pass

            print(f"{articles_added} articles")
            db.commit()

        except Exception as e:
            print(f"error: {str(e)[:50]}")
            stats["errors"] += 1
            db.rollback()

    print(f"\nPhase 3 Complete:")
    print(f"  Competitors processed: {stats['competitors_processed']}")
    print(f"  Articles cached: {stats['articles_cached']}")
    print(f"  Errors: {stats['errors']}")

    return stats


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse various date formats."""
    if not date_str:
        return None

    try:
        # Common formats
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(str(date_str).strip(), fmt)
            except ValueError:
                continue

        # Try dateutil
        try:
            from dateutil import parser
            return parser.parse(str(date_str))
        except Exception:
            pass

    except Exception:
        pass

    return None


# ==============================================================================
# MAIN
# ==============================================================================

async def main():
    """Main entry point."""
    print("="*60)
    print("CERTIFY INTEL - COMPREHENSIVE DATA POPULATION")
    print("="*60)
    print(f"Started: {datetime.utcnow().isoformat()}")

    db = SessionLocal()

    try:
        # Phase 1: Extract products from existing data
        phase1_stats = extract_products_from_existing_data(db)

        # Phase 2: AI product discovery (if still missing)
        try:
            phase2_stats = await discover_products_with_ai(db)
        except Exception as e:
            print(f"Phase 2 error: {e}")
            phase2_stats = {"products_created": 0}

        # Phase 3: News population
        phase3_stats = populate_news_cache(db)

        # Final summary
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)

        # Check final coverage
        total_comp = db.query(Competitor).filter(Competitor.is_deleted == False).count()
        with_products = db.query(CompetitorProduct.competitor_id).distinct().count()
        total_products = db.query(CompetitorProduct).count()
        total_news = db.query(NewsArticleCache).count()
        with_news = db.query(NewsArticleCache.competitor_id).distinct().count()

        print(f"\nProduct Coverage:")
        print(f"  Competitors with products: {with_products}/{total_comp} ({100*with_products/total_comp:.1f}%)")
        print(f"  Total products: {total_products}")

        print(f"\nNews Coverage:")
        print(f"  Competitors with news: {with_news}/{total_comp} ({100*with_news/total_comp:.1f}%)")
        print(f"  Total articles: {total_news}")

        print(f"\nCompleted: {datetime.utcnow().isoformat()}")

    except Exception as e:
        import logging
        logging.exception(f"Fatal error: {e}")
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
