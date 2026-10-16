from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.case import permissions as case_permissions
from app.modules.workflow.repository import RequestEventRepository
from app.modules.files import permissions, storage
from app.modules.files.repository import FileRepository
from app.modules.files.schemas import FileDownloadRead, file_read
from app.database.models.workflow import DeliverableSubtype, FileRole, LifecycleStatus, RefKind, WorkType

routerFile = APIRouter(prefix="/api/requests", tags=["Request Files"])

# Baca: semua peran, di-scope is_readable lalu visible_files.
_READ_ROLE = require_roles(
    "superadmin", "admin_department", "drafter_checker", "drafter", "yoshimoto_reviewer"
)
# Unggah berkas request: pihak Koribali. Aturan per role berkas dicek di handler.
_UPLOAD_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")



# ===== Helper =====
def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def resolve_file_name(file_name: str | None, upload: UploadFile) -> str:
    """Nama sebagaimana didefinisikan worker, atau nama berkas unggahan bila kosong.
    Tidak divalidasi terhadap standar penamaan apa pun (larangan 2)."""
    name = (file_name or "").strip() or (upload.filename or "").strip()
    if not name:
        raise _unprocessable("fileName is required when the uploaded file has no name")
    if len(name) > 255:
        raise _unprocessable("fileName must be at most 255 characters")
    return name


async def _load_visible(db: AsyncSession, actor: CurrentUser, request_id: str, file_id: str):
    """404 bila request tidak terbaca, berkas tidak ada, atau berkas di luar scope actor."""
    await case_permissions.load_readable_request(db, request_id, actor)
    f = await FileRepository.get_in_request(db, request_id, file_id)
    if f is None:
        raise permissions.file_not_found()
    visible = await permissions.visible_files(db, actor, request_id, [f])
    if not visible:
        raise permissions.file_not_found()
    return visible[0]



# ===== Read =====
@routerFile.get("/{request_id}/files")
async def list_files(
    request_id: str,
    file_role: FileRole | None = Query(default=None, alias="fileRole"),
    work_type: WorkType | None = Query(default=None, alias="workType"),
    case_id: str | None = Query(default=None, alias="caseId"),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    await case_permissions.load_readable_request(db, request_id, actor)
    rows = await FileRepository.list_in_request(
        db, request_id, file_role=file_role, work_type=work_type, case_id=case_id,
    )
    visible = await permissions.visible_files(db, actor, request_id, rows)
    return success_response(
        data=[file_read(f, versions, permissions.current_version(actor, f, versions)) for f, versions in visible],
        message="Request files retrieved",
    )


@routerFile.get("/{request_id}/files/{file_id}")
async def get_file(
    request_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    f, versions = await _load_visible(db, actor, request_id, file_id)
    return success_response(
        data=file_read(f, versions, permissions.current_version(actor, f, versions)),
        message="Request file retrieved",
    )


@routerFile.get("/{request_id}/files/{file_id}/download")
async def get_download_url(
    request_id: str,
    file_id: str,
    version_id: str | None = Query(default=None, alias="versionId"),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    """URL unduh bertanda tangan berumur pendek. Gateway tidak pernah mengalirkan isi berkas."""
    f, versions = await _load_visible(db, actor, request_id, file_id)
    version = None
    if f.file_role in permissions.VERSIONED_ROLES:
        if version_id is None:
            version = permissions.current_version(actor, f, versions)
        else:
            version = next((v for v in versions if v.id == version_id), None)
        if version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        storage_ref = version.storage_ref
    elif version_id is not None:
        raise _unprocessable("versionId is only valid for versioned files")
    else:
        storage_ref = f.storage_ref

    url = await storage.download_url(storage_ref, f.file_name)
    return success_response(
        data=FileDownloadRead(
            url=url,
            file_name=f.file_name,
            version_id=version.id if version is not None else None,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.FILE_DOWNLOAD_URL_SECONDS),
        ),
        message="Download URL created",
    )



# ===== Unggah berkas request =====
async def _create_reference(db, actor, req, upload, file_name, ref_kind):
    if ref_kind is None:
        raise _unprocessable("refKind is required for fileRole reference")
    await permissions.ensure_can_add_reference(db, actor, req)
    path = await storage.store_upload(req.id, upload)
    try:
        return await FileRepository.create_unversioned(
            db,
            request_id=req.id,
            uploader_id=actor.id,
            file_role=FileRole.reference,
            ref_kind=ref_kind,
            file_name=file_name,
            storage_ref=path,
        )
    except Exception:
        await storage.discard([path])
        raise



async def _create_versioned(db, actor, req, upload, file_name, file_role, work_type, case_id, subtype):
    if file_role == FileRole.deliverable:
        if work_type is None or case_id is None or subtype is None:
            raise _unprocessable("workType, caseId, and deliverableSubtype are required for fileRole deliverable")
        await permissions.load_deliverable_case(db, actor, req, work_type, case_id, subtype)
    else:
        await permissions.ensure_can_add_concept_brief(db, actor, req)
    path = await storage.store_upload(req.id, upload)
    try:
        return await FileRepository.create_versioned(
            db,
            request_id=req.id,
            uploader_id=actor.id,
            file_role=file_role,
            file_name=file_name,
            storage_ref=path,
            calculation_case_id=case_id if work_type == WorkType.calculation else None,
            drawing_case_id=case_id if work_type == WorkType.drawing else None,
            deliverable_subtype=subtype,
        )
    except Exception:
        await storage.discard([path])
        raise



@routerFile.post("/{request_id}/files")
async def upload_file(
    request_id: str,
    file: UploadFile = File(...),
    file_role: FileRole = Form(alias="fileRole"),
    file_name: str | None = Form(default=None, alias="fileName"),
    ref_kind: RefKind | None = Form(default=None, alias="refKind"),
    work_type: WorkType | None = Form(default=None, alias="workType"),
    case_id: str | None = Form(default=None, alias="caseId"),
    deliverable_subtype: DeliverableSubtype | None = Form(default=None, alias="deliverableSubtype"),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_UPLOAD_ROLE),
):
    """Berkas baru milik request. note_attachment dan check_result tidak lewat sini,
    karena keduanya menempel ke peristiwa (lihat routers/attachments.py)."""
    req = await case_permissions.load_readable_request(db, request_id, actor)
    name = resolve_file_name(file_name, file)
    if ref_kind is not None and file_role != FileRole.reference:
        raise _unprocessable("refKind is only valid for fileRole reference")
    if file_role != FileRole.deliverable and (work_type or case_id or deliverable_subtype):
        raise _unprocessable("workType, caseId, and deliverableSubtype are only valid for fileRole deliverable")

    if file_role == FileRole.reference:
        row = await _create_reference(db, actor, req, file, name, ref_kind)
    elif file_role in permissions.VERSIONED_ROLES:
        row = await _create_versioned(
            db, actor, req, file, name, file_role, work_type, case_id, deliverable_subtype,
        )
    else:
        raise _unprocessable(f"fileRole '{file_role.value}' cannot be uploaded here")

    versions = sorted(row.versions, key=lambda v: v.version_no, reverse=True)
    return success_response(
        data=file_read(row, versions, permissions.current_version(actor, row, versions)),
        status_code=status.HTTP_201_CREATED,
        message="File uploaded",
    )
    
    
    
# ===== Versi baru =====
@routerFile.post("/{request_id}/files/{file_id}/versions")
async def upload_version(
    request_id: str,
    file_id: str,
    file: UploadFile = File(...),
    previous_version_id: str = Form(alias="previousVersionId", min_length=1),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_UPLOAD_ROLE),
):
    """Versi baru deliverable atau concept_brief. Lineage dinyatakan eksplisit: worker menunjuk
    versi yang digantikan, dan hanya versi aktif yang boleh digantikan"""
    req = await case_permissions.load_readable_request(db, request_id, actor)
    f = await FileRepository.get_in_request(db, request_id, file_id)
    if f is None:
        raise permissions.file_not_found()
    if f.file_role not in permissions.VERSIONED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Files with fileRole '{f.file_role.value}' have no versions",
        )
    await permissions.ensure_can_add_version(db, actor, req, f)

    def ensure_active(row):
        previous = next((v for v in row.versions if v.id == previous_version_id), None)
        if previous is None:
            raise _unprocessable("previousVersionId does not reference a version of this file")
        if previous.lifecycle_status != LifecycleStatus.active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="previousVersionId must be the active version of this file",
            )
        return previous

    # Cek dini sebelum mengunggah, supaya kesalahan umum tidak meninggalkan objek.
    ensure_active(f)
    path = await storage.store_upload(req.id, file)
    try:
        # Kunci request, lalu baca ulang versi: dua unggahan bersamaan yang menunjuk versi
        # yang sama berjalan bergiliran, dan yang kedua ditolak 409.
        await RequestEventRepository.get_for_update(db, request_id)
        f = await FileRepository.get_in_request(db, request_id, file_id, refresh=True)
        if f is None:
            raise permissions.file_not_found()
        f = await FileRepository.add_version(
            db, f, ensure_active(f), uploader_id=actor.id, storage_ref=path,
        )
    except Exception:
        await storage.discard([path])
        raise

    versions = sorted(f.versions, key=lambda v: v.version_no, reverse=True)
    return success_response(
        data=file_read(f, versions, permissions.current_version(actor, f, versions)),
        status_code=status.HTTP_201_CREATED,
        message="File version uploaded",
    )