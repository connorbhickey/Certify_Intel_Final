"""
Certify Intel - System Prompt & Knowledge Base Pydantic Schemas
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SystemPromptBase(BaseModel):
    key: str
    content: str
    category: Optional[str] = None
    description: Optional[str] = None


class SystemPromptCreate(SystemPromptBase):
    pass


class SystemPromptResponse(SystemPromptBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeBaseItemBase(BaseModel):
    title: str
    content_text: str
    source_type: Optional[str] = "manual"
    is_active: Optional[bool] = True


class KnowledgeBaseItemCreate(KnowledgeBaseItemBase):
    pass


class KnowledgeBaseItemResponse(KnowledgeBaseItemBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserSavedPromptCreate(BaseModel):
    name: str
    prompt_type: str = "executive_summary"
    content: str


class UserSavedPromptUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    is_default: Optional[bool] = None


class UserSavedPromptResponse(BaseModel):
    id: int
    user_id: int
    name: str
    prompt_type: str
    content: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
