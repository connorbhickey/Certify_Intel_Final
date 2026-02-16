"""
Certify Intel - Admin Router

Endpoints:
- GET  /api/admin/system-prompts/{key} - Get system prompt by key
- POST /api/admin/system-prompts - Create/update user-specific prompt
- GET  /api/admin/system-prompts - List all system prompts
- GET  /api/admin/system-prompts/categories - List prompt categories
- GET  /api/admin/knowledge-base - List active KB items
- POST /api/admin/knowledge-base - Add KB item
- DELETE /api/admin/knowledge-base/{item_id} - Soft-delete KB item
- POST /api/admin/knowledge-base/upload - Upload document to KB
- GET  /api/admin/data-providers/status - Data provider configuration status
- POST /api/admin/data-providers/test/{provider_name} - Test provider connectivity
"""

import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db, SystemPrompt, KnowledgeBaseItem
from dependencies import get_current_user
from schemas.prompts import (
    SystemPromptCreate, SystemPromptResponse,
    KnowledgeBaseItemCreate, KnowledgeBaseItemResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ============== System Prompts ==============


@router.get(
    "/system-prompts/categories",
)
def list_prompt_categories(db: Session = Depends(get_db)):
    """List all available prompt categories with counts."""
    from sqlalchemy import func as sa_func
    rows = db.query(
        SystemPrompt.category,
        sa_func.count(SystemPrompt.id)
    ).filter(
        SystemPrompt.user_id == None,  # noqa: E711
        SystemPrompt.category != None  # noqa: E711
    ).group_by(SystemPrompt.category).all()

    return [{"category": cat, "count": cnt} for cat, cnt in rows]


@router.get(
    "/system-prompts/{key}",
    response_model=SystemPromptResponse,
)
def get_system_prompt(
    key: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a system prompt by key (user-specific first, then global fallback)."""
    user_id = current_user.get("id") if current_user else None

    # Try user-specific prompt first
    prompt = db.query(SystemPrompt).filter(
        SystemPrompt.key == key,
        SystemPrompt.user_id == user_id
    ).first()

    # Fallback to global prompt
    if not prompt:
        prompt = db.query(SystemPrompt).filter(
            SystemPrompt.key == key,
            SystemPrompt.user_id == None  # noqa: E711
        ).first()

    if not prompt:
        default_content = ""
        if key == "dashboard_summary":
            default_content = (
                "You are Certify Health's competitive intelligence analyst. "
                "Generate a comprehensive, executive-level strategic summary "
                "using ONLY the LIVE data provided below."
            )
        elif key == "chat_persona":
            default_content = (
                "You are a competitive intelligence analyst for Certify "
                "Health. Always reference specific data points and "
                "competitor names when answering questions. Cite exact "
                "numbers and dates when available."
            )

        return SystemPromptResponse(key=key, content=default_content)
    return prompt


@router.post(
    "/system-prompts",
    response_model=SystemPromptResponse,
)
def update_system_prompt(
    prompt_data: SystemPromptCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update or create a user-specific system prompt."""
    user_id = current_user.get("id") if current_user else None

    prompt = db.query(SystemPrompt).filter(
        SystemPrompt.key == prompt_data.key,
        SystemPrompt.user_id == user_id
    ).first()

    if prompt:
        prompt.content = prompt_data.content
        if prompt_data.category:
            prompt.category = prompt_data.category
        if prompt_data.description:
            prompt.description = prompt_data.description
        prompt.updated_at = datetime.utcnow()
    else:
        prompt = SystemPrompt(
            key=prompt_data.key,
            content=prompt_data.content,
            category=prompt_data.category,
            description=prompt_data.description,
            user_id=user_id
        )
        db.add(prompt)

    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("/system-prompts")
def list_system_prompts(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all system prompts, optionally filtered by category.

    Returns global prompts merged with any user-specific overrides.
    Categories: dashboard, battlecards, news, discovery, competitor,
    knowledge_base
    """
    user_id = current_user.get("id") if current_user else None

    # Get all global prompts
    query = db.query(SystemPrompt).filter(
        SystemPrompt.user_id == None  # noqa: E711
    )
    if category:
        query = query.filter(SystemPrompt.category == category)
    global_prompts = query.order_by(SystemPrompt.key).all()

    # Get user-specific overrides
    user_query = db.query(SystemPrompt).filter(
        SystemPrompt.user_id == user_id
    )
    if category:
        user_query = user_query.filter(
            SystemPrompt.category == category
        )
    user_prompts = {p.key: p for p in user_query.all()}

    # Merge: user overrides take precedence
    results = []
    for gp in global_prompts:
        if gp.key in user_prompts:
            up = user_prompts[gp.key]
            results.append({
                "id": up.id,
                "key": up.key,
                "category": up.category or gp.category,
                "description": up.description or gp.description,
                "content": up.content,
                "updated_at": (
                    up.updated_at.isoformat() if up.updated_at else None
                ),
                "is_custom": True,
            })
        else:
            results.append({
                "id": gp.id,
                "key": gp.key,
                "category": gp.category,
                "description": gp.description,
                "content": gp.content,
                "updated_at": (
                    gp.updated_at.isoformat() if gp.updated_at else None
                ),
                "is_custom": False,
            })

    return results


# ============== Knowledge Base ==============


@router.get(
    "/knowledge-base",
    response_model=List[KnowledgeBaseItemResponse],
)
def get_knowledge_base_items(db: Session = Depends(get_db)):
    """Get all active knowledge base items."""
    return db.query(KnowledgeBaseItem).filter(
        KnowledgeBaseItem.is_active == True  # noqa: E712
    ).order_by(KnowledgeBaseItem.created_at.desc()).all()


@router.post(
    "/knowledge-base",
    response_model=KnowledgeBaseItemResponse,
)
def add_knowledge_base_item(
    item: KnowledgeBaseItemCreate,
    db: Session = Depends(get_db)
):
    """Add a new item to the knowledge base."""
    new_item = KnowledgeBaseItem(
        title=item.title,
        content_text=item.content_text,
        source_type=item.source_type,
        is_active=item.is_active
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


@router.delete("/knowledge-base/{item_id}")
def delete_knowledge_base_item(
    item_id: int, db: Session = Depends(get_db)
):
    """Soft delete a knowledge base item."""
    item = db.query(KnowledgeBaseItem).filter(
        KnowledgeBaseItem.id == item_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.is_active = False
    db.commit()
    return {"message": "Item deleted"}


@router.post("/knowledge-base/upload")
async def upload_knowledge_base_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: Optional[str] = Form("general"),
    tags: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Upload a document to the Knowledge Base.

    Supported file types: PDF, DOCX, TXT, MD, HTML.
    The document will be ingested, chunked, and indexed for RAG retrieval.
    """
    import os
    import json
    import tempfile

    allowed_extensions = {'.pdf', '.docx', '.txt', '.md', '.html'}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {file_ext}. "
                f"Allowed: {', '.join(allowed_extensions)}"
            )
        )

    content = await file.read()
    file_size = len(content)

    max_size = 50 * 1024 * 1024  # 50MB
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File too large. Maximum size: 50MB, "
                f"got: {file_size / (1024*1024):.1f}MB"
            )
        )

    doc_title = title if title else os.path.splitext(file.filename)[0]
    tag_list = [t.strip() for t in tags.split(',')] if tags else []

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=file_ext
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        extracted_text = ""

        if file_ext == '.pdf':
            try:
                import PyPDF2
                with open(tmp_path, 'rb') as pdf_file:
                    reader = PyPDF2.PdfReader(pdf_file)
                    for page in reader.pages:
                        extracted_text += page.extract_text() + "\n"
            except Exception as e:
                logger.error(f"Failed to extract PDF text: {e}")
                raise HTTPException(
                    status_code=400,
                    detail="Failed to extract text from the uploaded PDF file"
                )

        elif file_ext == '.docx':
            try:
                from docx import Document
                doc = Document(tmp_path)
                extracted_text = "\n".join(
                    [para.text for para in doc.paragraphs]
                )
            except Exception as e:
                logger.error(f"Failed to extract DOCX text: {e}")
                raise HTTPException(
                    status_code=400,
                    detail="Failed to extract text from the uploaded DOCX file"
                )

        elif file_ext in {'.txt', '.md', '.html'}:
            extracted_text = content.decode('utf-8', errors='replace')

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No text content could be extracted from the file"
            )

        new_item = KnowledgeBaseItem(
            title=doc_title,
            content_text=extracted_text,
            content_type=file_ext.lstrip('.'),
            source=f"upload:{file.filename}",
            source_type="upload",
            category=category,
            tags=json.dumps(tag_list) if tag_list else None,
            extra_metadata=json.dumps({
                "original_filename": file.filename,
                "file_size": file_size,
                "uploaded_by": current_user.get("email", "unknown"),
                "upload_date": datetime.utcnow().isoformat(),
                "char_count": len(extracted_text),
                "word_count": len(extracted_text.split())
            }),
            is_active=True
        )

        db.add(new_item)
        db.commit()
        db.refresh(new_item)

        # Try to ingest into vector store (non-blocking)
        ingestion_status = "pending"
        chunk_count = 0

        try:
            from knowledge_base import KnowledgeBase
            kb = KnowledgeBase()

            result = await kb.ingest_document(
                file_path=tmp_path,
                uploaded_by=current_user.get("email", "unknown"),
                metadata={
                    "title": doc_title,
                    "source": f"upload:{file.filename}",
                    "category": category,
                    "kb_item_id": new_item.id
                }
            )

            if result.get("status") == "success":
                ingestion_status = "indexed"
                chunk_count = result.get("chunks_created", 0)
            else:
                ingestion_status = result.get("status", "failed")
        except Exception:
            ingestion_status = "error: ingestion failed"

        return {
            "id": new_item.id,
            "title": new_item.title,
            "content_type": new_item.content_type,
            "category": new_item.category,
            "tags": new_item.tags,
            "source": new_item.source,
            "char_count": len(extracted_text),
            "word_count": len(extracted_text.split()),
            "ingestion_status": ingestion_status,
            "chunk_count": chunk_count,
            "message": "Document uploaded successfully"
        }

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ============== Data Providers ==============


@router.get("/data-providers/status")
async def get_data_provider_status(
    current_user: dict = Depends(get_current_user)
):
    """Get configuration status of all enterprise data providers."""
    try:
        from data_providers import get_all_provider_status
        return {"providers": get_all_provider_status()}
    except ImportError:
        return {
            "providers": [],
            "message": "Data providers module not installed"
        }


@router.post("/data-providers/test/{provider_name}")
async def test_data_provider(
    provider_name: str,
    current_user: dict = Depends(get_current_user)
):
    """Test connectivity to a specific data provider."""
    try:
        from data_providers import get_provider
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Data providers module not installed"
        )

    provider = get_provider(provider_name)
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider_name}' not found or not configured",
        )

    result = await provider.test_connection()
    return {
        "provider": provider_name,
        "success": result.get("success", False),
        "message": result.get("message", ""),
        "latency_ms": result.get("latency_ms", 0),
    }
