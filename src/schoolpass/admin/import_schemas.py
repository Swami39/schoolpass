from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImportRowError(BaseModel):
    row_number: int
    message: str


class ImportValidateResponse(BaseModel):
    import_type: str
    content_digest: str
    row_count: int
    valid_row_count: int
    errors: list[ImportRowError]


class ImportApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_digest: str = Field(min_length=64, max_length=64)
    confirm: bool = False


class ImportApplyResponse(BaseModel):
    import_type: str
    content_digest: str
    row_count: int
    applied_count: int
    skipped_count: int
    status: str


class ImportTemplateResponse(BaseModel):
    import_type: str
    columns: list[str]
    csv_header_line: str


class ImportHistoryItem(BaseModel):
    id: UUID
    action: str
    import_type: str | None
    row_count: int | None
    status: str | None
    content_digest: str | None
    created_at: datetime


class ImportHistoryResponse(BaseModel):
    items: list[ImportHistoryItem]
