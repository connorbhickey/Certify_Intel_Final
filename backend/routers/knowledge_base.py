"""
Certify Intel - Knowledge Base Import API Router (v5.0.8)

Provides endpoints for importing competitor data from the client-provided
knowledge base folder.

All imported data is labeled as "Source: Certify Health" (source_type="client_provided").
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import database dependencies
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Competitor, DataSource

# Import the knowledge base importer
from knowledge_base_importer import (
    KnowledgeBaseImporter,
    ImportResult,
    CompetitorData,
    get_all_competitor_names,
    normalize_competitor_name
)

router = APIRouter(prefix="/api/knowledge-base", tags=["Knowledge Base"])


# ==============================================================================
# DEPENDENCY
# ==============================================================================

def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==============================================================================
# PYDANTIC MODELS
# ==============================================================================

class FilePreview(BaseModel):
    """File preview information."""
    path: str
    filename: str
    file_type: str
    size_bytes: int


class CompetitorPreview(BaseModel):
    """Competitor preview information."""
    name: str
    canonical_name: str
    source_file: str
    website: Optional[str] = None
    pricing_model: Optional[str] = None
    employee_count: Optional[str] = None
    fields_populated: int


class ImportPreviewResponse(BaseModel):
    """Response for import preview."""
    total_files: int
    files_parsed: int
    competitors_found: int
    unique_competitors: int
    competitors: List[CompetitorPreview]
    errors: List[str]
    warnings: List[str]


class ImportRequest(BaseModel):
    """Request to perform import."""
    dry_run: bool = False
    overwrite_existing: bool = False  # If true, overwrite all; if false, fill gaps only


class ImportedCompetitor(BaseModel):
    """Result of importing a single competitor."""
    name: str
    id: int
    is_new: bool
    fields_updated: int
    source_file: str


class ImportResponse(BaseModel):
    """Response for import operation."""
    success: bool
    competitors_imported: int
    competitors_updated: int
    competitors_skipped: int
    imported: List[ImportedCompetitor]
    errors: List[str]


class VerificationQueueItem(BaseModel):
    """Item in the verification queue."""
    source_id: int
    competitor_id: int
    competitor_name: str
    field_name: str
    value: str
    source_file: str
    is_verified: bool
    confidence_score: int


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@router.get("/scan", response_model=List[FilePreview])
def scan_knowledge_base_folder():
    """
    Scan the knowledge base folder and return list of supported files.

    This is a quick operation that doesn't parse file contents.
    """
    try:
        importer = KnowledgeBaseImporter()
        files = importer.scan_folder()

        return [
            FilePreview(
                path=f.path,
                filename=f.filename,
                file_type=f.file_type,
                size_bytes=f.size_bytes
            )
            for f in files
        ]
    except Exception as e:
        logger.error(f"Knowledge base scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Knowledge base scan failed. Please try again.")


@router.get("/preview", response_model=ImportPreviewResponse)
def preview_import():
    """
    Preview what would be imported from the knowledge base folder.

    Parses all files and returns a summary of competitors that would be imported.
    Does not make any database changes.
    """
    try:
        importer = KnowledgeBaseImporter()
        result = importer.extract_all()

        # Count populated fields for each competitor
        competitor_previews = []
        for comp in result.competitors:
            fields_populated = sum([
                1 for field in [
                    comp.website, comp.pricing_model, comp.base_price,
                    comp.product_categories, comp.key_features, comp.integration_partners,
                    comp.target_segments, comp.customer_count, comp.employee_count,
                    comp.year_founded, comp.headquarters, comp.funding_total,
                    comp.g2_rating, comp.notes
                ] if field
            ])

            competitor_previews.append(CompetitorPreview(
                name=comp.name,
                canonical_name=comp.canonical_name,
                source_file=comp.source_file.split(";")[0].strip(),  # First source
                website=comp.website,
                pricing_model=comp.pricing_model,
                employee_count=comp.employee_count,
                fields_populated=fields_populated
            ))

        return ImportPreviewResponse(
            total_files=result.total_files_scanned,
            files_parsed=result.files_parsed,
            competitors_found=result.competitors_found,
            unique_competitors=result.unique_competitors,
            competitors=competitor_previews,
            errors=result.errors,
            warnings=result.warnings
        )

    except Exception as e:
        logger.error(f"Knowledge base preview failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Knowledge base preview failed. Please try again.")


@router.post("/import", response_model=ImportResponse)
def import_knowledge_base(
    request: ImportRequest,
    db: Session = Depends(get_db)
):
    """
    Import competitors from the knowledge base folder into the database.

    All imported data is labeled with source_type="client_provided" and
    source_name="Certify Health Knowledge Base".

    Args:
        request.dry_run: If true, only preview changes without saving
        request.overwrite_existing: If true, overwrite all fields; if false, only fill gaps
    """
    try:
        importer = KnowledgeBaseImporter()
        result = importer.extract_all()

        imported = []
        updated_count = 0
        new_count = 0
        skipped_count = 0
        errors = result.errors.copy()

        for comp_data in result.competitors:
            try:
                # Check if competitor already exists
                existing = db.query(Competitor).filter(
                    Competitor.name.ilike(comp_data.canonical_name)
                ).first()

                if existing:
                    if request.dry_run:
                        # Preview mode - just count
                        imported.append(ImportedCompetitor(
                            name=comp_data.canonical_name,
                            id=existing.id,
                            is_new=False,
                            fields_updated=0,
                            source_file=comp_data.source_file
                        ))
                        updated_count += 1
                        continue

                    # Update existing competitor (fill gaps only or overwrite)
                    fields_updated = _update_competitor(
                        db, existing, comp_data,
                        overwrite=request.overwrite_existing
                    )

                    imported.append(ImportedCompetitor(
                        name=comp_data.canonical_name,
                        id=existing.id,
                        is_new=False,
                        fields_updated=fields_updated,
                        source_file=comp_data.source_file
                    ))
                    updated_count += 1

                else:
                    if request.dry_run:
                        # Preview mode - just count
                        imported.append(ImportedCompetitor(
                            name=comp_data.canonical_name,
                            id=0,
                            is_new=True,
                            fields_updated=0,
                            source_file=comp_data.source_file
                        ))
                        new_count += 1
                        continue

                    # Create new competitor
                    new_comp = _create_competitor(db, comp_data)

                    imported.append(ImportedCompetitor(
                        name=comp_data.canonical_name,
                        id=new_comp.id,
                        is_new=True,
                        fields_updated=0,
                        source_file=comp_data.source_file
                    ))
                    new_count += 1

            except Exception as e:
                logger.error(f"Error importing {comp_data.canonical_name}: {e}")
                errors.append(f"Error importing {comp_data.canonical_name}")
                skipped_count += 1

        if not request.dry_run:
            db.commit()

        return ImportResponse(
            success=True,
            competitors_imported=new_count,
            competitors_updated=updated_count,
            competitors_skipped=skipped_count,
            imported=imported,
            errors=errors
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Knowledge base import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Knowledge base import failed. Please try again.")


@router.get("/competitor-names")
def get_known_competitor_names():
    """
    Get list of all 74 known competitor names from Certify Health.

    These are the canonical competitor names that the importer will recognize.
    """
    return {
        "count": len(get_all_competitor_names()),
        "competitors": sorted([name.title() for name in get_all_competitor_names()])
    }


@router.get("/verification-queue", response_model=List[VerificationQueueItem])
def get_verification_queue(
    competitor_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get list of unverified client-provided data for review.

    Returns all DataSource records with source_type="client_provided"
    that haven't been verified yet.
    """
    query = db.query(DataSource).filter(
        DataSource.source_type == "client_provided",
        DataSource.is_verified == False
    )

    if competitor_id:
        query = query.filter(DataSource.competitor_id == competitor_id)

    sources = query.all()

    # Get competitor names
    competitor_ids = list(set(s.competitor_id for s in sources))
    competitors = {
        c.id: c.name
        for c in db.query(Competitor).filter(Competitor.id.in_(competitor_ids)).all()
    }

    return [
        VerificationQueueItem(
            source_id=s.id,
            competitor_id=s.competitor_id,
            competitor_name=competitors.get(s.competitor_id, "Unknown"),
            field_name=s.field_name,
            value=s.current_value or "",
            source_file=s.source_url or "",
            is_verified=s.is_verified,
            confidence_score=s.confidence_score or 0
        )
        for s in sources
    ]


@router.post("/verification/approve/{source_id}")
def approve_verification(
    source_id: int,
    corrected_value: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Approve (verify) a client-provided data point.

    Optionally provide a corrected_value to update the stored value.
    """
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.is_verified = True
    source.verified_by = "manual"
    source.verification_date = datetime.utcnow()

    if corrected_value:
        source.previous_value = source.current_value
        source.current_value = corrected_value

        # Also update the competitor field
        competitor = db.query(Competitor).filter(Competitor.id == source.competitor_id).first()
        if competitor and hasattr(competitor, source.field_name):
            setattr(competitor, source.field_name, corrected_value)

    db.commit()

    return {"success": True, "message": f"Data point {source_id} verified"}


@router.post("/verification/reject/{source_id}")
def reject_verification(
    source_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Reject a client-provided data point.

    The data will be removed from the competitor record.
    """
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Clear the value from competitor
    competitor = db.query(Competitor).filter(Competitor.id == source.competitor_id).first()
    if competitor and hasattr(competitor, source.field_name):
        setattr(competitor, source.field_name, None)

    # Mark source as rejected (we'll use a special flag)
    source.is_verified = True
    source.verified_by = f"rejected: {reason or 'No reason given'}"
    source.verification_date = datetime.utcnow()
    source.current_value = None

    db.commit()

    return {"success": True, "message": f"Data point {source_id} rejected"}


@router.post("/verification/bulk-approve")
def bulk_approve_verification(
    source_ids: List[int],
    db: Session = Depends(get_db)
):
    """
    Bulk approve multiple data points at once.
    """
    approved = 0

    for source_id in source_ids:
        source = db.query(DataSource).filter(DataSource.id == source_id).first()
        if source:
            source.is_verified = True
            source.verified_by = "bulk_manual"
            source.verification_date = datetime.utcnow()
            approved += 1

    db.commit()

    return {"success": True, "approved": approved}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _create_competitor(db: Session, comp_data: CompetitorData) -> Competitor:
    """Create a new competitor from imported data."""

    # Create the competitor record
    competitor = Competitor(
        name=comp_data.canonical_name.title(),
        website=comp_data.website,
        status=comp_data.status or "Active",
        threat_level=comp_data.threat_level or "Medium",

        # Pricing
        pricing_model=comp_data.pricing_model,
        base_price=comp_data.base_price,
        price_unit=comp_data.price_unit,

        # Product
        product_categories=comp_data.product_categories,
        key_features=comp_data.key_features,
        integration_partners=comp_data.integration_partners,
        certifications=comp_data.certifications,

        # Market
        target_segments=comp_data.target_segments,
        customer_size_focus=comp_data.customer_size_focus,
        geographic_focus=comp_data.geographic_focus,
        customer_count=comp_data.customer_count,
        customer_acquisition_rate=comp_data.customer_acquisition_rate,
        key_customers=comp_data.key_customers,

        # Company
        employee_count=comp_data.employee_count,
        employee_growth_rate=comp_data.employee_growth_rate,
        year_founded=comp_data.year_founded,
        headquarters=comp_data.headquarters,
        funding_total=comp_data.funding_total,
        latest_round=comp_data.latest_round,
        pe_vc_backers=comp_data.pe_vc_backers,

        # Digital
        website_traffic=comp_data.website_traffic,
        social_following=comp_data.social_following,
        g2_rating=comp_data.g2_rating,

        # Features
        has_pxp=comp_data.has_patient_intake,
        has_rcm=comp_data.has_insurance_verification,
        has_payments=comp_data.has_payments,
        has_patient_mgmt=comp_data.has_patient_portal,

        # Notes
        notes=comp_data.notes,
        recent_launches=comp_data.recent_launches,

        # Metadata
        created_at=datetime.utcnow(),
        last_updated=datetime.utcnow()
    )

    db.add(competitor)
    db.flush()  # Get the ID

    # Create DataSource records for each populated field
    _create_data_sources(db, competitor.id, comp_data)

    return competitor


def _update_competitor(
    db: Session,
    existing: Competitor,
    comp_data: CompetitorData,
    overwrite: bool = False
) -> int:
    """
    Update an existing competitor with imported data.

    Args:
        db: Database session
        existing: Existing competitor record
        comp_data: New data from import
        overwrite: If True, overwrite all fields. If False, only fill gaps.

    Returns:
        Number of fields updated
    """
    fields_updated = 0

    field_mapping = {
        "website": "website",
        "pricing_model": "pricing_model",
        "base_price": "base_price",
        "price_unit": "price_unit",
        "product_categories": "product_categories",
        "key_features": "key_features",
        "integration_partners": "integration_partners",
        "certifications": "certifications",
        "target_segments": "target_segments",
        "customer_size_focus": "customer_size_focus",
        "geographic_focus": "geographic_focus",
        "customer_count": "customer_count",
        "customer_acquisition_rate": "customer_acquisition_rate",
        "key_customers": "key_customers",
        "employee_count": "employee_count",
        "employee_growth_rate": "employee_growth_rate",
        "year_founded": "year_founded",
        "headquarters": "headquarters",
        "funding_total": "funding_total",
        "latest_round": "latest_round",
        "pe_vc_backers": "pe_vc_backers",
        "website_traffic": "website_traffic",
        "social_following": "social_following",
        "g2_rating": "g2_rating",
        "notes": "notes",
        "recent_launches": "recent_launches",
    }

    for data_field, db_field in field_mapping.items():
        new_value = getattr(comp_data, data_field, None)

        if not new_value:
            continue

        existing_value = getattr(existing, db_field, None)

        # Only update if overwrite=True or existing is empty
        if overwrite or not existing_value:
            setattr(existing, db_field, new_value)
            fields_updated += 1

            # Create DataSource record for the update
            _create_single_data_source(
                db, existing.id, db_field, new_value, comp_data.source_file
            )

    # Update boolean fields (OR logic - set true if new data has it)
    bool_fields = [
        ("has_patient_intake", "has_pxp"),
        ("has_insurance_verification", "has_rcm"),
        ("has_payments", "has_payments"),
        ("has_patient_portal", "has_patient_mgmt"),
    ]

    for data_field, db_field in bool_fields:
        if getattr(comp_data, data_field, False):
            if not getattr(existing, db_field, False):
                setattr(existing, db_field, True)
                fields_updated += 1

    existing.last_updated = datetime.utcnow()

    return fields_updated


def _create_data_sources(db: Session, competitor_id: int, comp_data: CompetitorData):
    """Create DataSource records for all populated fields in imported data."""

    fields_to_track = [
        ("website", comp_data.website),
        ("pricing_model", comp_data.pricing_model),
        ("base_price", comp_data.base_price),
        ("price_unit", comp_data.price_unit),
        ("product_categories", comp_data.product_categories),
        ("key_features", comp_data.key_features),
        ("integration_partners", comp_data.integration_partners),
        ("certifications", comp_data.certifications),
        ("target_segments", comp_data.target_segments),
        ("customer_size_focus", comp_data.customer_size_focus),
        ("geographic_focus", comp_data.geographic_focus),
        ("customer_count", comp_data.customer_count),
        ("customer_acquisition_rate", comp_data.customer_acquisition_rate),
        ("key_customers", comp_data.key_customers),
        ("employee_count", comp_data.employee_count),
        ("employee_growth_rate", comp_data.employee_growth_rate),
        ("year_founded", comp_data.year_founded),
        ("headquarters", comp_data.headquarters),
        ("funding_total", comp_data.funding_total),
        ("latest_round", comp_data.latest_round),
        ("pe_vc_backers", comp_data.pe_vc_backers),
        ("website_traffic", comp_data.website_traffic),
        ("social_following", comp_data.social_following),
        ("g2_rating", comp_data.g2_rating),
        ("notes", comp_data.notes),
        ("recent_launches", comp_data.recent_launches),
    ]

    for field_name, value in fields_to_track:
        if value:
            _create_single_data_source(
                db, competitor_id, field_name, value, comp_data.source_file
            )


def _create_single_data_source(
    db: Session,
    competitor_id: int,
    field_name: str,
    value: str,
    source_file: str
):
    """Create a single DataSource record for a field."""

    # Check if source already exists
    existing = db.query(DataSource).filter(
        DataSource.competitor_id == competitor_id,
        DataSource.field_name == field_name,
        DataSource.source_type == "client_provided"
    ).first()

    if existing:
        # Update existing source
        existing.current_value = value
        existing.source_url = f"file://{source_file}"
        existing.extracted_at = datetime.utcnow()
    else:
        # Create new source
        source = DataSource(
            competitor_id=competitor_id,
            field_name=field_name,
            current_value=value,
            source_type="client_provided",
            source_name="Certify Health Knowledge Base",
            source_url=f"file://{source_file}",
            extraction_method="kb_import",
            confidence_score=85,  # High confidence - client provided
            confidence_level="high",
            source_reliability="B",  # Usually reliable
            information_credibility=2,  # Probably true
            is_verified=False,  # Awaiting verification
            extracted_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        db.add(source)
