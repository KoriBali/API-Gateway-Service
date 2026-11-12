from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.database.models.intake import BrandLine, CoverSourceKind
from app.modules.files import storage
from app.modules.intake import permissions
from app.modules.intake.cover.extract import CoverUnreadable, detect_kind, extract_cover
from app.modules.intake.repository import (
    CoverUploadRepository,
    ProjectRepository,
    RequestRepository,
    StagedCoverConflict,
)
from app.modules.intake.schemas import (
    CoverDraft,
    CoverExtractRead,
    CoverHints,
    CoverSource,
    CoverWarning,
    RequestNoDuplicate,
)
from app.utils.response import success_response


routerCover = APIRouter(prefix="/api/requests", tags=["Requests"])

# Sama dengan create request: semua peran kecuali yoshimoto_reviewer.
_ANY_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")

_CONTENT_TYPES = {
    CoverSourceKind.pdf: "application/pdf",
    CoverSourceKind.excel: "application/vnd.ms-excel",
}
_DEFAULT_NAMES = {CoverSourceKind.pdf: "cover.pdf", CoverSourceKind.excel: "cover.xls"}


@routerCover.post("/cover-extract")
async def extract_request_cover(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    """Baca cover YS (PDF atau Excel form) menjadi draf isian POST /api/requests.

    File disimpan sebagai cover upload staged milik actor, menggantikan yang lama, dan
    baru menjadi berkas request_cover saat request dibuat dengan coverUploadId."""
    data = await storage.read_upload(file)
    kind = detect_kind(data)
    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"reason": "unsupported_file_type",
                    "message": "Upload a PDF or an Excel (.xls) request form"},
        )
    try:
        result = await run_in_threadpool(extract_cover, data, kind)
    except CoverUnreadable as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": exc.reason, "message": exc.message},
        ) from exc

    file_name = (file.filename or "").strip() or _DEFAULT_NAMES[kind]
    source = CoverSource(file_name=file_name, **result.source)
    draft = CoverDraft.model_validate(result.draft)
    warnings = [CoverWarning(**w) for w in result.warnings]

    path = await storage.store_cover(data, _CONTENT_TYPES[kind])
    try:
        upload, old_ref = await CoverUploadRepository.replace_staged(
            db,
            user_id=actor.id,
            source_kind=kind,
            file_name=file_name,
            storage_ref=path,
            extracted={
                "source": source.model_dump(mode="json", by_alias=True),
                "draft": draft.model_dump(mode="json", by_alias=True),
                "warnings": [w.model_dump(by_alias=True) for w in warnings],
                "raw": result.raw,
                "flags": result.flags,
            },
        )
    except StagedCoverConflict as exc:
        await storage.discard([path])
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "cover_extract_in_progress",
                    "message": "Another cover extract of this user is running; try again"},
        ) from exc
    except Exception:
        await storage.discard([path])
        raise
    await storage.discard([old_ref])

    return success_response(
        data=CoverExtractRead(
            cover_upload_id=upload.id,
            source=source,
            draft=draft,
            warnings=warnings,
            raw=result.raw,
            hints=await _hints(db, actor, draft),
        ),
        status_code=status.HTTP_201_CREATED,
        message="Cover extracted",
    )


async def _hints(db: AsyncSession, actor: CurrentUser, draft: CoverDraft) -> CoverHints:
    """Lookup bantuan, tidak pernah mengisi draf: project YS ber-PJ No sama dan request
    bernomor sama. Jumlah kembar dihitung dari semua request; rinciannya hanya yang terbaca."""
    project = None
    if draft.pj_no:
        project = await ProjectRepository.find_by_identity(
            db, request_form=BrandLine.ys, scope_code="", pj_no=draft.pj_no,
        )
    others = await RequestRepository.list_by_request_no(db, draft.request_no) if draft.request_no else []
    visible = [r for r in others if permissions.can_read_request(actor, r)]
    return CoverHints(
        project_id=project.id if project is not None else None,
        request_no_duplicate_count=len(others),
        request_no_duplicates=[RequestNoDuplicate.model_validate(r) for r in visible],
    )
