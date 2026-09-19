from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.admin import import_csv as import_svc
from schoolpass.admin.import_schemas import (
    ImportApplyResponse,
    ImportHistoryItem,
    ImportHistoryResponse,
    ImportTemplateResponse,
    ImportValidateResponse,
)
from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.api.routes.admin import _ctx, _request_id
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import ValidationFailed

router = APIRouter(prefix="/api/v1/admin", tags=["admin-imports"])


@router.get("/imports/types/{import_type}/template", response_model=ImportTemplateResponse)
async def admin_import_template(
    import_type: str,
    principal: Annotated[Principal, Depends(require("imports:read"))],
) -> ImportTemplateResponse:
    columns, header = import_svc.template_for(import_type)
    return ImportTemplateResponse(import_type=import_type, columns=columns, csv_header_line=header)


@router.post("/imports/{import_type}/validate", response_model=ImportValidateResponse)
async def admin_import_validate(
    import_type: str,
    principal: Annotated[Principal, Depends(require("imports:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    file: Annotated[UploadFile, File()],
) -> ImportValidateResponse:
    raw = await file.read()
    if not raw:
        raise ValidationFailed("CSV file is empty")
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            return await import_svc.validate_import(session, _ctx(principal), import_type=import_type, raw=raw)


@router.post("/imports/{import_type}/apply", response_model=ImportApplyResponse)
async def admin_import_apply(
    request: Request,
    import_type: str,
    content_digest: Annotated[str, Form()],
    confirm: Annotated[bool, Form()],
    principal: Annotated[Principal, Depends(require("imports:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    file: Annotated[UploadFile, File()],
) -> ImportApplyResponse:
    if not confirm:
        raise ValidationFailed("confirm must be true to apply import")
    raw = await file.read()
    if not raw:
        raise ValidationFailed("CSV file is empty")
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            applied, skipped, row_count = await import_svc.apply_import(
                session,
                _ctx(principal),
                import_type=import_type,
                raw=raw,
                content_digest_expected=content_digest,
                request_id=_request_id(request),
            )
    digest = import_svc.content_digest(raw)
    return ImportApplyResponse(
        import_type=import_type,
        content_digest=digest,
        row_count=row_count,
        applied_count=applied,
        skipped_count=skipped,
        status="completed",
    )


@router.get("/imports/history", response_model=ImportHistoryResponse)
async def admin_import_history(
    principal: Annotated[Principal, Depends(require("imports:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    limit: int = Query(default=25, ge=1, le=100),
) -> ImportHistoryResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await import_svc.list_import_history(session, _ctx(principal), limit=limit)
    return ImportHistoryResponse(items=[ImportHistoryItem.model_validate(r) for r in rows])
