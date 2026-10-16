from datetime import datetime

from app.utils.base_schema import CamelBaseModel
from app.database.models.workflow import (
    DeliverableSubtype,
    FileRole,
    LifecycleStatus,
    RefKind,
    WorkType,
)


# Input berkas berupa multipart form, jadi field-nya dideklarasikan di router (Form, File),
# bukan sebagai schema JSON.



# ===== Output =====
class FileVersionRead(CamelBaseModel):
    """storage_ref tidak pernah diekspos: berkas hanya diunduh lewat URL bertanda tangan."""
    id: str
    request_file_id: str
    revision_round_id: str | None = None
    version_no: int
    lifecycle_status: LifecycleStatus
    previous_version_id: str | None = None
    uploaded_by_user_id: str
    uploaded_at: datetime



class RequestFileRead(CamelBaseModel):
    id: str
    request_id: str
    file_role: FileRole
    ref_kind: RefKind | None = None
    # Work type dan case induk deliverable, dibaca dari penunjuk case yang terisi.
    work_type: WorkType | None = None
    case_id: str | None = None
    deliverable_subtype: DeliverableSubtype | None = None
    request_event_id: str | None = None
    file_name: str
    uploaded_by_user_id: str
    created_at: datetime
    # Role berversi saja. Untuk yoshimoto_reviewer: versi yang berlaku saat submit terakhir.
    current_version: FileVersionRead | None = None
    # Terbaru dulu. Kosong untuk role tidak berversi.
    versions: list[FileVersionRead] = []



class FileDownloadRead(CamelBaseModel):
    url: str
    file_name: str
    # Kosong untuk role tidak berversi.
    version_id: str | None = None
    expires_at: datetime



def file_read(f, versions: list, current) -> RequestFileRead:
    """Bangun RequestFileRead dari baris ORM. versions dan current sudah disaring scope baca."""
    if f.calculation_case_id is not None:
        work_type, case_id = WorkType.calculation, f.calculation_case_id
    elif f.drawing_case_id is not None:
        work_type, case_id = WorkType.drawing, f.drawing_case_id
    else:
        work_type, case_id = None, None
    return RequestFileRead(
        id=f.id,
        request_id=f.request_id,
        file_role=f.file_role,
        ref_kind=f.ref_kind,
        work_type=work_type,
        case_id=case_id,
        deliverable_subtype=f.deliverable_subtype,
        request_event_id=f.request_event_id,
        file_name=f.file_name,
        uploaded_by_user_id=f.uploaded_by_user_id,
        created_at=f.created_at,
        current_version=FileVersionRead.model_validate(current) if current is not None else None,
        versions=[FileVersionRead.model_validate(v) for v in versions],
    )
