"""
Certify Intel - Pydantic Schema Models

Organized by domain for use across routers and main.py.
"""

from schemas.competitors import (  # noqa: F401
    CompetitorCreate,
    CompetitorResponse,
    CorrectionRequest,
    ScrapeRequest,
    BulkUpdateRequest,
    BulkDeleteRequest,
    BulkExportRequest,
    SearchResult,
)
from schemas.auth import (  # noqa: F401
    UserResponse,
    UserInviteRequest,
)
from schemas.prompts import (  # noqa: F401
    SystemPromptBase,
    SystemPromptCreate,
    SystemPromptResponse,
    KnowledgeBaseItemBase,
    KnowledgeBaseItemCreate,
    KnowledgeBaseItemResponse,
    UserSavedPromptCreate,
    UserSavedPromptUpdate,
    UserSavedPromptResponse,
)
from schemas.products import (  # noqa: F401
    ProductCreate,
    ProductResponse,
    PricingTierCreate,
    PricingTierResponse,
    FeatureMatrixCreate,
    CustomerCountCreate,
    CustomerCountResponse,
    CustomerCountVerifyRequest,
)
from schemas.common import (  # noqa: F401
    DataChangeSubmission,
    WinLossCreate,
    WebhookCreate,
    SubscriptionCreate,
    SubscriptionUpdate,
    WebVitalsMetric,
)
