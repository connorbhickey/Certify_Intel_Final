"""
Certify Intel - Product Discovery API Router (v5.1.0)

API endpoints for product discovery, tracking, and coverage monitoring.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from database import get_db, Competitor, CompetitorProduct, DataSource
from sqlalchemy.orm import Session

# Import product discovery
try:
    from product_discovery_crawler import (
        ProductDiscoveryCrawler,
        ProductDiscoveryService,
        DiscoveredProduct,
        ProductDiscoveryResult
    )
    DISCOVERY_AVAILABLE = True
except ImportError:
    DISCOVERY_AVAILABLE = False
    print("Product discovery crawler not available")


router = APIRouter(prefix="/api/products", tags=["Products"])


# ==============================================================================
# PYDANTIC MODELS
# ==============================================================================

class ProductResponse(BaseModel):
    id: int
    competitor_id: int
    product_name: str
    product_category: str
    product_subcategory: Optional[str] = None
    description: Optional[str] = None
    key_features: Optional[str] = None
    target_segment: Optional[str] = None
    is_primary_product: bool = False
    market_position: Optional[str] = None
    created_at: Optional[str] = None
    last_updated: Optional[str] = None

    class Config:
        from_attributes = True


class ProductCreateRequest(BaseModel):
    competitor_id: int
    product_name: str
    product_category: str
    product_subcategory: Optional[str] = None
    description: Optional[str] = None
    key_features: Optional[str] = None
    target_segment: Optional[str] = None
    is_primary_product: bool = False


class DiscoveryStatusResponse(BaseModel):
    status: str  # idle, running, completed
    current_competitor: Optional[str] = None
    progress: int = 0
    total: int = 0
    products_found: int = 0
    errors: List[str] = []


class CoverageResponse(BaseModel):
    total_competitors: int
    competitors_with_products: int
    coverage_percentage: float
    total_products: int
    products_by_category: dict
    competitors_missing_products: List[dict]


# Global discovery status
_discovery_status = {
    "status": "idle",
    "current_competitor": None,
    "progress": 0,
    "total": 0,
    "products_found": 0,
    "errors": []
}


# ==============================================================================
# PRODUCT CRUD ENDPOINTS
# ==============================================================================

@router.get("/", response_model=List[ProductResponse])
async def list_all_products(
    competitor_id: Optional[int] = None,
    category: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List all products, optionally filtered by competitor or category."""
    query = db.query(CompetitorProduct)

    if competitor_id:
        query = query.filter(CompetitorProduct.competitor_id == competitor_id)

    if category:
        query = query.filter(CompetitorProduct.product_category.ilike(f"%{category}%"))

    products = query.order_by(
        CompetitorProduct.competitor_id,
        CompetitorProduct.is_primary_product.desc()
    ).offset(offset).limit(limit).all()

    return products


@router.get("/competitor/{competitor_id}", response_model=List[ProductResponse])
async def get_competitor_products(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Get all products for a specific competitor."""
    products = db.query(CompetitorProduct).filter(
        CompetitorProduct.competitor_id == competitor_id
    ).order_by(
        CompetitorProduct.is_primary_product.desc(),
        CompetitorProduct.product_name
    ).all()

    return products


@router.post("/", response_model=ProductResponse)
async def create_product(
    product: ProductCreateRequest,
    db: Session = Depends(get_db)
):
    """Manually create a product record."""
    # Verify competitor exists
    competitor = db.query(Competitor).filter(Competitor.id == product.competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    # Check for duplicate
    existing = db.query(CompetitorProduct).filter(
        CompetitorProduct.competitor_id == product.competitor_id,
        CompetitorProduct.product_name.ilike(product.product_name)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Product already exists")

    new_product = CompetitorProduct(
        competitor_id=product.competitor_id,
        product_name=product.product_name,
        product_category=product.product_category,
        product_subcategory=product.product_subcategory,
        description=product.description,
        key_features=product.key_features,
        target_segment=product.target_segment,
        is_primary_product=product.is_primary_product,
        created_at=datetime.utcnow(),
        last_updated=datetime.utcnow()
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    # Create DataSource record
    source = DataSource(
        competitor_id=product.competitor_id,
        field_name=f"product:{product.product_name}",
        current_value=product.product_name,
        source_type="manual",
        source_name="Manual Entry",
        extraction_method="manual",
        confidence_score=90,
        confidence_level="high",
        is_verified=True,
        verified_by="manual",
        verification_date=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    db.add(source)
    db.commit()

    return new_product


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    """Delete a product record."""
    product = db.query(CompetitorProduct).filter(CompetitorProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(product)
    db.commit()

    return {"message": "Product deleted", "id": product_id}


# ==============================================================================
# PRODUCT DISCOVERY ENDPOINTS
# ==============================================================================

@router.get("/discover/{competitor_id}")
async def discover_competitor_products(
    competitor_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Discover products for a specific competitor.
    Runs in background and returns immediately.
    """
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(status_code=500, detail="Product discovery crawler not available")

    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    if not competitor.website:
        raise HTTPException(status_code=400, detail="Competitor has no website")

    # Run discovery in background
    background_tasks.add_task(
        _run_single_discovery,
        competitor.id,
        competitor.name,
        competitor.website
    )

    return {
        "message": f"Product discovery started for {competitor.name}",
        "competitor_id": competitor_id
    }


@router.post("/discover/all")
async def discover_all_products(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Discover products for ALL competitors.
    Runs in background. Check status with /discover/status.
    """
    global _discovery_status  # noqa: F824

    if not DISCOVERY_AVAILABLE:
        raise HTTPException(status_code=500, detail="Product discovery crawler not available")

    if _discovery_status["status"] == "running":
        raise HTTPException(status_code=400, detail="Discovery already running")

    # Count competitors
    total = db.query(Competitor).filter(
        Competitor.is_deleted == False,
        Competitor.website.isnot(None)
    ).count()

    _discovery_status = {
        "status": "running",
        "current_competitor": None,
        "progress": 0,
        "total": total,
        "products_found": 0,
        "errors": []
    }

    # Run in background
    background_tasks.add_task(_run_full_discovery)

    return {
        "message": "Full product discovery started",
        "total_competitors": total
    }


@router.get("/discover/status", response_model=DiscoveryStatusResponse)
async def get_discovery_status():
    """Get the status of the current discovery job."""
    return _discovery_status


@router.post("/discover/stop")
async def stop_discovery():
    """Stop the current discovery job."""
    if _discovery_status["status"] != "running":
        raise HTTPException(status_code=400, detail="No discovery running")

    _discovery_status["status"] = "stopped"
    return {"message": "Discovery stop requested"}


# ==============================================================================
# COVERAGE ENDPOINTS
# ==============================================================================

@router.get("/coverage", response_model=CoverageResponse)
async def get_product_coverage(db: Session = Depends(get_db)):
    """Get product coverage statistics."""
    # Total competitors
    total_competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False
    ).count()

    # Competitors with products
    competitors_with_products = db.query(
        CompetitorProduct.competitor_id
    ).distinct().count()

    # Total products
    total_products = db.query(CompetitorProduct).count()

    # Products by category
    from sqlalchemy import func
    category_counts = db.query(
        CompetitorProduct.product_category,
        func.count(CompetitorProduct.id)
    ).group_by(CompetitorProduct.product_category).all()

    products_by_category = {cat: count for cat, count in category_counts}

    # Competitors missing products
    missing = db.query(Competitor).filter(
        Competitor.is_deleted == False,
        ~Competitor.id.in_(
            db.query(CompetitorProduct.competitor_id).distinct()
        )
    ).limit(20).all()

    competitors_missing = [
        {"id": c.id, "name": c.name, "website": c.website}
        for c in missing
    ]

    coverage_pct = (competitors_with_products / total_competitors * 100) if total_competitors > 0 else 0

    return CoverageResponse(
        total_competitors=total_competitors,
        competitors_with_products=competitors_with_products,
        coverage_percentage=round(coverage_pct, 1),
        total_products=total_products,
        products_by_category=products_by_category,
        competitors_missing_products=competitors_missing
    )


@router.get("/categories")
async def get_product_categories(db: Session = Depends(get_db)):
    """Get all unique product categories."""
    from sqlalchemy import func

    categories = db.query(
        CompetitorProduct.product_category,
        func.count(CompetitorProduct.id).label("count")
    ).group_by(
        CompetitorProduct.product_category
    ).order_by(
        func.count(CompetitorProduct.id).desc()
    ).all()

    return [
        {"category": cat, "count": count}
        for cat, count in categories
    ]


@router.get("/comparison")
async def compare_products(
    competitor_ids: str = Query(..., description="Comma-separated competitor IDs"),
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Compare products across multiple competitors.
    Returns a matrix of products by competitor.
    """
    ids = [int(x.strip()) for x in competitor_ids.split(",")]

    competitors = db.query(Competitor).filter(
        Competitor.id.in_(ids)
    ).all()

    result = {}
    for comp in competitors:
        query = db.query(CompetitorProduct).filter(
            CompetitorProduct.competitor_id == comp.id
        )

        if category:
            query = query.filter(
                CompetitorProduct.product_category.ilike(f"%{category}%")
            )

        products = query.all()

        result[comp.name] = [
            {
                "id": p.id,
                "name": p.product_name,
                "category": p.product_category,
                "description": p.description,
                "is_primary": p.is_primary_product
            }
            for p in products
        ]

    return result


# ==============================================================================
# BACKGROUND TASKS
# ==============================================================================

async def _run_single_discovery(competitor_id: int, name: str, website: str):
    """Run product discovery for a single competitor."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        async with ProductDiscoveryCrawler(use_ai=True) as crawler:
            result = await crawler.discover_products(name, website, competitor_id)

            # Save products
            for product in result.products_found:
                existing = db.query(CompetitorProduct).filter(
                    CompetitorProduct.competitor_id == competitor_id,
                    CompetitorProduct.product_name.ilike(product.product_name)
                ).first()

                if not existing:
                    new_product = CompetitorProduct(
                        competitor_id=competitor_id,
                        product_name=product.product_name,
                        product_category=product.product_category,
                        description=product.description,
                        target_segment=product.target_segment,
                        is_primary_product=product.is_primary_product,
                        created_at=datetime.utcnow(),
                        last_updated=datetime.utcnow()
                    )
                    db.add(new_product)

            # Update competitor's product_categories
            comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if comp and result.products_found:
                categories = list(set(p.product_category for p in result.products_found))
                comp.product_categories = "; ".join(categories)

            db.commit()
            logger.info(f"[Discovery] {name}: {len(result.products_found)} products found")

    except Exception as e:
        logger.error(f"[Discovery] Error for {name}: {e}")
        db.rollback()
    finally:
        db.close()


async def _run_full_discovery():
    """Run product discovery for all competitors."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        competitors = db.query(Competitor).filter(
            Competitor.is_deleted == False,
            Competitor.website.isnot(None)
        ).all()

        async with ProductDiscoveryCrawler(use_ai=True) as crawler:
            for i, comp in enumerate(competitors):
                if _discovery_status["status"] == "stopped":
                    break

                _discovery_status["current_competitor"] = comp.name
                _discovery_status["progress"] = i + 1

                try:
                    result = await crawler.discover_products(
                        comp.name,
                        comp.website,
                        comp.id
                    )

                    # Save products
                    for product in result.products_found:
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
                            _discovery_status["products_found"] += 1

                    # Update competitor's product_categories
                    if result.products_found:
                        categories = list(set(p.product_category for p in result.products_found))
                        comp.product_categories = "; ".join(categories)

                    db.commit()

                except Exception as e:
                    logger.error(f"Product discovery failed for {comp.name}: {e}")
                    _discovery_status["errors"].append(f"{comp.name}: discovery failed")
                    db.rollback()

                # Rate limiting
                await asyncio.sleep(3)

        _discovery_status["status"] = "completed"
        _discovery_status["current_competitor"] = None

    except Exception as e:
        _discovery_status["status"] = "failed"
        logger.error(f"Product discovery failed: {e}", exc_info=True)
        _discovery_status["errors"].append("Discovery process failed")
    finally:
        db.close()


# ==============================================================================
# QUICK AUDIT - Fill product data using AI
# ==============================================================================

@router.post("/audit/quick")
async def quick_product_audit(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Quick audit: Use AI to fill product data for competitors missing it.
    Analyzes existing data and competitor websites to populate products.
    """
    # Count competitors needing products
    missing_count = db.query(Competitor).filter(
        Competitor.is_deleted == False,
        ~Competitor.id.in_(
            db.query(CompetitorProduct.competitor_id).distinct()
        )
    ).count()

    background_tasks.add_task(_run_quick_audit)

    return {
        "message": "Quick product audit started",
        "competitors_to_process": missing_count
    }


async def _run_quick_audit():
    """Run quick audit to fill product data."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        # Get competitors without products
        competitors = db.query(Competitor).filter(
            Competitor.is_deleted == False,
            Competitor.website.isnot(None),
            ~Competitor.id.in_(
                db.query(CompetitorProduct.competitor_id).distinct()
            )
        ).all()

        print(f"[Quick Audit] Processing {len(competitors)} competitors...")

        async with ProductDiscoveryCrawler(use_ai=True) as crawler:
            for comp in competitors:
                try:
                    result = await crawler.discover_products(
                        comp.name,
                        comp.website,
                        comp.id
                    )

                    for product in result.products_found:
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

                    if result.products_found:
                        categories = list(set(p.product_category for p in result.products_found))
                        comp.product_categories = "; ".join(categories)

                    db.commit()
                    logger.info(f"[Quick Audit] {comp.name}: {len(result.products_found)} products")

                except Exception as e:
                    logger.error(f"[Quick Audit] Error for {comp.name}: {e}")
                    db.rollback()

                await asyncio.sleep(2)

        logger.info("[Quick Audit] Complete!")

    except Exception as e:
        logger.error(f"[Quick Audit] Fatal error: {e}", exc_info=True)
    finally:
        db.close()
