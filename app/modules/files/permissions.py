from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.database.models.intake import Request
from app.database.models.workflow import FileRole, FileVersion, LifecycleStatus, RequestFile
from app.modules.assignment.repository import AssignmentRepository
from app.modules.intake import permissions as intake_permissions
from app.modules.files.repository import FileRepository


# Role yang lokasi fisiknya dicatat per versi di file_versions (DD 7.9).
VERSIONED_ROLES = frozenset({FileRole.deliverable, FileRole.concept_brief})



def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def file_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")



# ===== Izin tulis =====
async def ensure_can_add_reference(db: AsyncSession, actor: CurrentUser, request: Request) -> None:
    """Bahan rujukan: yang boleh mengelola request (superadmin, admin_department, pembuat),
    atau pengerja dengan assignment aktif. Pemanggil sudah memastikan request terbaca."""
    try:
        # Memakai aturan intake apa adanya, tanpa salinan aturan izin.
        intake_permissions.ensure_can_manage_request(actor, request)
        return
    except HTTPException:
        pass
    if not await AssignmentRepository.has_active(db, request.id, actor.id):
        raise _forbidden("Only a user who manages this request or has an active assignment can add references")



# ===== Scope baca =====
async def visible_files(
    db: AsyncSession, actor: CurrentUser, request_id: str, files: list[RequestFile],
) -> list[tuple[RequestFile, list[FileVersion]]]:
    """Berkas dan versi yang boleh dilihat actor, versi terbaru dulu.

    Pihak Koribali melihat semuanya. yoshimoto_reviewer hanya melihat apa yang sudah
    menyeberang ke sisinya: reference, lampiran peristiwa tingkat request (feedback, cancel),
    dan untuk deliverable hanya versi yang berlaku saat submit terakhir. Hasil pemeriksaan,
    lampiran pemeriksaan, brief konsep, dan pekerjaan sesudah submit tidak terlihat."""
    def newest_first(f: RequestFile) -> list[FileVersion]:
        return sorted(f.versions, key=lambda v: v.version_no, reverse=True)

    if actor.role != "yoshimoto_reviewer":
        return [(f, newest_first(f)) for f in files]

    cutoff = await FileRepository.last_submit_at(db, request_id)
    request_level = await FileRepository.request_level_event_ids(
        db, [f.request_event_id for f in files if f.file_role == FileRole.note_attachment],
    )
    visible = []
    for f in files:
        if f.file_role == FileRole.reference:
            visible.append((f, []))
        elif f.file_role == FileRole.note_attachment and f.request_event_id in request_level:
            visible.append((f, []))
        elif f.file_role == FileRole.deliverable and cutoff is not None:
            submitted = [v for v in newest_first(f) if v.uploaded_at <= cutoff]
            if submitted:
                visible.append((f, submitted[:1]))
    return visible


def current_version(actor: CurrentUser, f: RequestFile, versions: list[FileVersion]) -> FileVersion | None:
    """Versi yang ditampilkan dan diunduh bila versionId tidak dikirim. Pihak Koribali: versi aktif.
    yoshimoto_reviewer: satu-satunya versi yang terlihat olehnya."""
    if f.file_role not in VERSIONED_ROLES or not versions:
        return None
    if actor.role == "yoshimoto_reviewer":
        return versions[0]
    return next((v for v in versions if v.lifecycle_status == LifecycleStatus.active), None)
