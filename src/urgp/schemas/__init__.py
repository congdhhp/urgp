"""URGP Pydantic schemas — request/response models for API endpoints.

Schemas define the API contract and are used for:
- Request validation (automatic via FastAPI)
- Response serialization
- OpenAPI documentation generation

Reference: docs/05-technical-design.md § Data Contract Payload
"""

from urgp.schemas.ingest import (
    ArtifactSchema,
    CIMetadataSchema,
    CommitHashSchema,
    IngestPayload,
)
from urgp.schemas.notifications import NotificationRequest
from urgp.schemas.responses import (
    DLQCountResponse,
    IngestAcceptedResponse,
    IngestDuplicateResponse,
    IngestInProgressResponse,
    RateLimitExceededResponse,
    ServiceUnavailableResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)

__all__ = [
    # Ingest
    "CommitHashSchema",
    "ArtifactSchema",
    "CIMetadataSchema",
    "IngestPayload",
    "NotificationRequest",
    # Responses
    "IngestAcceptedResponse",
    "IngestDuplicateResponse",
    "IngestInProgressResponse",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
    "RateLimitExceededResponse",
    "DLQCountResponse",
    "ServiceUnavailableResponse",
]
