from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.database.models.intake import Request
from app.database.models.workflow import (
    DeliverableSubtype,
    FileRole,
    FileVersion,
    LifecycleStatus,
    RequestFile,
    WorkType,
)
from app.modules.assignment.repository import AssignmentRepository
from app.modules.case import permissions as case_permissions
from app.modules.case.repository import CaseRepository
from app.modules.intake import permissions as intake_permissions
from app.modules.files.repository import FileRepository


# Role yang lokasi fisiknya dicatat per versi di file_versions
VERSIONED_ROLES = frozenset({FileRole.deliverable, FileRole.concept_brief})

# Sub-jenis deliverable per work type case induk. Aturan aplikasi, bukan constraint
SUBTYPES_OF: dict[WorkType, frozenset[DeliverableSubtype]] = {
    WorkType.calculation: frozenset({
        DeliverableSubtype.calculation_report,
        DeliverableSubtype.calculation_file,
        DeliverableSubtype.schematic_drawing,
    }),
    WorkType.drawing: frozenset({
        DeliverableSubtype.main_sheet,
        DeliverableSubtype.detail_sheet,
        DeliverableSubtype.bill_of_materials,
    }),
}


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

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




async def load_deliverable_case(
    db: AsyncSession, actor: CurrentUser, request: Request,
    work_type: WorkType, case_id: str, subtype: DeliverableSubtype,
):
    """Case induk deliverable: harus ada di request ini, sub-jenis cocok dengan work type-nya,
    dan hanya owner case yang menyerahkan deliverable"""
    if subtype not in SUBTYPES_OF[work_type]:
        raise _unprocessable(f"deliverableSubtype '{subtype.value}' does not belong to workType '{work_type.value}'")
    case = await CaseRepository.get_in_request(db, work_type, request.id, case_id)
    if case is None:
        raise _unprocessable(f"caseId does not reference a {work_type.value} case of this request")
    case_permissions.ensure_owner(actor, case)
    return case



async def ensure_can_add_concept_brief(db: AsyncSession, actor: CurrentUser, request: Request) -> None:
    """admin_department pada request mana pun di departemennya, atau pengerja dengan assignment
    aktif di request ini. Pemanggil sudah memastikan request terbaca."""
    if actor.role == "admin_department":
        return
    if not await AssignmentRepository.has_active(db, request.id, actor.id):
        raise _forbidden("Only admin_department or a user with an active assignment can add a concept brief")



async def ensure_can_add_version(db: AsyncSession, actor: CurrentUser, request: Request, f: RequestFile) -> None:
    """Versi baru ikut aturan pembuatan berkasnya: deliverable oleh owner case induk saat ini
    (kepemilikan bisa sudah dialihkan), concept_brief oleh admin_department atau pengerja aktif."""
    if f.file_role == FileRole.deliverable:
        work_type = WorkType.calculation if f.calculation_case_id is not None else WorkType.drawing
        case = await CaseRepository.get_in_request(
            db, work_type, request.id, f.calculation_case_id or f.drawing_case_id,
        )
        case_permissions.ensure_owner(actor, case)
    else:
        await ensure_can_add_concept_brief(db, actor, request)




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
