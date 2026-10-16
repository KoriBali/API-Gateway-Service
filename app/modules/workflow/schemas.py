from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app.utils.base_schema import CamelBaseModel
from app.database.models.intake import DesignType, RequestStatus
from app.database.models.workflow import CheckResult, EventType, RevisionOrigin, WorkType


# Teks wajib: spasi di tepi dibuang dulu, jadi "   " ditolak 422.
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]



# ===== Input =====
class FeedbackCreate(CamelBaseModel):
    # Isi tanggapan dari pihak Yoshimoto, disimpan di revision_rounds.trigger_note.
    note: RequiredText
    # Work type yang perlu direvisi. Kosong = seluruh requests.design_type.
    work_scope: DesignType | None = None



class CancelCreate(CamelBaseModel):
    # Alasan wajib, disimpan di request_events.payload.
    reason: RequiredText



# ===== Output =====
class RequestEventRead(CamelBaseModel):
    id: str
    request_id: str
    actor_user_id: str
    event_type: EventType
    case_id: str | None = None
    work_type: WorkType | None = None
    check_result: CheckResult | None = None
    payload: dict | None = None
    occurred_at: datetime



class RevisionRoundRead(CamelBaseModel):
    id: str
    request_id: str
    check_event_id: str | None = None
    round_number: int
    work_scope: DesignType
    origin: RevisionOrigin
    round_label: str | None = None
    round_date: datetime
    trigger_note: str | None = None



class RequestEventResult(CamelBaseModel):
    """Respons setiap aksi peristiwa: status baru request, peristiwa yang tercatat,
    dan putaran revisi yang dibuka (hanya untuk feedback)."""
    status: RequestStatus
    event: RequestEventRead
    revision_round: RevisionRoundRead | None = None
    


# ===== Gerbang submit =====
class UncheckedCaseRead(CamelBaseModel):
    work_type: WorkType
    case_id: str
    title: str



class SubmitGateRead(CamelBaseModel):
    """Keadaan gerbang submit siklus berjalan, beserta keterangan yang menahannya."""
    can_submit: bool
    # Syarat 1 sampai 3 terpenuhi. Sama dengan rumus status prevention_check.
    prevention_check_ready: bool
    revision_round_id: str | None = None
    cycle_started_at: datetime | None = None
    checklist_id: str | None = None
    pending_items: int
    missing_work_types: list[WorkType]
    unchecked_cases: list[UncheckedCaseRead]
    # Syarat 4: case manual yang check-nya di siklus ini belum membawa berkas hasil pemeriksaan.
    cases_without_check_result: list[UncheckedCaseRead]
    # Keterangan saja, tidak menahan submit.
    cases_without_deliverable: list[UncheckedCaseRead]
