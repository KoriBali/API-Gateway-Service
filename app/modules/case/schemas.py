from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.utils.base_schema import CamelBaseModel
from app.database.models.calculation import PoleKind
from app.database.models.intake import RequestStatus
from app.database.models.workflow import CheckResult, WorkType
from app.modules.assignment.schemas import AssigneeRead


# Teks opsional: spasi di tepi dibuang, string kosong dianggap tidak diisi.
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]



# ===== Input =====
class CheckCreate(CamelBaseModel):
    check_result: CheckResult
    # Catatan temuan, disimpan di request_events.payload dan revision_rounds.trigger_note.
    # Wajib untuk has_findings. Berkas (hasil pemeriksaan, lampiran temuan) dilampirkan sesudah
    # peristiwa tercatat, jadi saat check dikirim belum ada berkas yang memuat temuannya
    note: OptionalText | None = None

    @model_validator(mode="after")
    def _note_for_findings(self):
        if self.note == "":
            self.note = None
        if self.check_result == CheckResult.has_findings and self.note is None:
            raise ValueError("note is required when checkResult is has_findings")
        return self



class OwnershipTransferCreate(CamelBaseModel):
    new_owner_user_id: str = Field(min_length=1)



# ===== Output =====
class CaseSummaryRead(CamelBaseModel):
    """Satu baris ringkasan case (calculation atau drawing) beserta keadaan pemeriksaannya."""
    id: str
    work_type: WorkType
    title: str
    case_label: str | None = None
    pole_kind: PoleKind
    created_by_user_id: str
    owner_user_id: str
    owner: AssigneeRead
    # False = owner tidak punya assignment aktif di work type ini
    owner_has_active_assignment: bool
    ready_for_check_at: datetime | None = None
    ready_for_check_by_user_id: str | None = None
    last_check_at: datetime | None = None
    last_check_result: CheckResult | None = None
    last_checked_by_user_id: str | None = None
    in_check_queue: bool
    # Sudah punya check sesudah feedback terakhir 
    checked_in_current_cycle: bool
    
    has_active_deliverable: bool
    last_deliverable_uploaded_at: datetime | None = None
    new_version_after_ready_for_check: bool
    new_version_after_check: bool

    created_at: datetime
    updated_at: datetime



class CheckQueueItemRead(CamelBaseModel):
    request_id: str
    request_no: str | None = None
    request_subject: str | None = None
    request_status: RequestStatus
    work_type: WorkType
    case_id: str
    title: str
    case_label: str | None = None
    owner: AssigneeRead
    ready_for_check_at: datetime
    ready_for_check_by_user_id: str
    # Ada versi deliverable yang lahir sesudah tanda siap dicek ini.
    new_version_after_ready_for_check: bool
