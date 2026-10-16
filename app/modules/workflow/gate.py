"""Gerbang submit dan status prevention_check. Keduanya dihitung dari data, tidak pernah disimpan
sebagai kolom penanda.

File ini tidak meng-import app.modules.case.repository maupun app.modules.intake, karena
keduanya memanggil apply_prevention_status di transaksinya sendiri."""
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database.models.intake import Request, RequestStatus
from app.database.models.workflow import (
    ChecklistItemStatus,
    EventType,
    FileRole,
    FileVersion,
    LifecycleStatus,
    NcChecklist,
    NcChecklistItem,
    RequestEvent,
    RequestFile,
    WorkType,
)
from app.modules.assignment.permissions import WORK_TYPES_OF
from app.modules.case.tables import CASE_FILE_FK, CASE_MODEL
from app.modules.workflow.repository import RequestEventRepository

# Status yang diisi sistem dari rumus prevention_check. Status lain hanya berubah lewat peristiwa.
PRE_SUBMIT_STATUSES = (RequestStatus.internal, RequestStatus.prevention_check)



@dataclass
class UncheckedCase:
    work_type: WorkType
    case_id: str
    title: str



@dataclass
class GateState:
    """Bahan gerbang submit untuk siklus submit berjalan."""
    revision_round_id: str | None
    cycle_started_at: datetime | None
    checklist_id: str | None
    pending_items: int
    missing_work_types: list[WorkType] = field(default_factory=list)
    unchecked_cases: list[UncheckedCase] = field(default_factory=list)
    # Syarat 4: case manual yang check-nya di siklus ini belum ditempeli berkas check_result.
    cases_without_check_result: list[UncheckedCase] = field(default_factory=list)
    # Keterangan saja: case tanpa versi aktif deliverable. Tetap wajib diperiksa (syarat 3).
    cases_without_deliverable: list[UncheckedCase] = field(default_factory=list)

    @property
    def prevention_check_ready(self) -> bool:
        """Syarat 1 sampai 3 status prevention_check: checklist ada, tiap work type punya case,
        setiap case diperiksa di siklus ini. Isi checklist belum dinilai."""
        return self.checklist_id is not None and not self.missing_work_types and not self.unchecked_cases

    @property
    def can_submit(self) -> bool:
        """Gerbang submit: syarat prevention_check, tidak ada item pending (syarat 1), dan setiap
        case manual punya check di siklus ini yang ditempeli berkas check_result (syarat 4)."""
        return (
            self.prevention_check_ready
            and self.pending_items == 0
            and not self.cases_without_check_result
        )


async def current_checklist(db: AsyncSession, request_id: str, revision_round_id: str | None) -> NcChecklist | None:
    """Checklist siklus submit berjalan. revision_round_id kosong = siklus pertama."""
    stmt = select(NcChecklist).where(NcChecklist.request_id == request_id)
    if revision_round_id is None:
        stmt = stmt.where(NcChecklist.revision_round_id.is_(None))
    else:
        stmt = stmt.where(NcChecklist.revision_round_id == revision_round_id)
    return await db.scalar(stmt)



async def evaluate(db: AsyncSession, req: Request) -> GateState:
    revision_round_id, started_at = await RequestEventRepository.current_cycle(db, req.id)
    checklist = await current_checklist(db, req.id, revision_round_id)

    pending = 0
    if checklist is not None:
        pending = await db.scalar(
            select(func.count()).select_from(NcChecklistItem).where(
                NcChecklistItem.nc_checklist_id == checklist.id,
                NcChecklistItem.item_status == ChecklistItemStatus.pending,
            )
        ) or 0

    state = GateState(
        revision_round_id=revision_round_id,
        cycle_started_at=started_at,
        checklist_id=checklist.id if checklist is not None else None,
        pending_items=pending,
    )

    for work_type, model in CASE_MODEL.items():
        # Syarat 3: setiap case yang ada, termasuk work type di luar design_type.
        checked = exists().where(
            RequestEvent.request_id == req.id,
            RequestEvent.case_id == model.id,
            RequestEvent.work_type == work_type,
            RequestEvent.event_type == EventType.check,
        )
        if started_at is not None:
            checked = checked.where(RequestEvent.occurred_at > started_at)

        # Case manual: minimal satu versi aktif deliverable berupa file unggahan. Dibaca saat
        # gerbang dinilai, bukan dari kolom penanda.
        active_deliverable = (
            select(RequestFile.id)
            .join(FileVersion, FileVersion.request_file_id == RequestFile.id)
            .where(
                CASE_FILE_FK[work_type] == model.id,
                RequestFile.file_role == FileRole.deliverable,
                FileVersion.lifecycle_status == LifecycleStatus.active,
            )
        )
        has_deliverable = active_deliverable.exists()
        is_manual = active_deliverable.where(FileVersion.storage_ref.is_not(None)).exists()

        # Syarat 4: check di siklus ini yang ditempeli berkas check_result.
        check_event = aliased(RequestEvent)
        checked_with_result = exists().where(
            check_event.request_id == req.id,
            check_event.case_id == model.id,
            check_event.work_type == work_type,
            check_event.event_type == EventType.check,
            exists().where(
                RequestFile.request_event_id == check_event.id,
                RequestFile.file_role == FileRole.check_result,
            ),
        )
        if started_at is not None:
            checked_with_result = checked_with_result.where(check_event.occurred_at > started_at)

        rows = (await db.execute(
            select(model.id, model.title, checked, has_deliverable, is_manual, checked_with_result)
            .where(model.request_id == req.id)
            .order_by(model.created_at, model.id)
        )).all()
        # Syarat 2: keberadaan minimal satu case, bukan perbandingan jumlah (larangan 1).
        if not rows and work_type in WORK_TYPES_OF[req.design_type]:
            state.missing_work_types.append(work_type)
        for case_id, title, is_checked, deliverable, manual, with_result in rows:
            case = UncheckedCase(work_type=work_type, case_id=case_id, title=title)
            if not is_checked:
                state.unchecked_cases.append(case)
            if manual and not with_result:
                state.cases_without_check_result.append(case)
            if not deliverable:
                state.cases_without_deliverable.append(case)

    return state



async def apply_prevention_status(db: AsyncSession, req: Request) -> None:
    """Isi requests.status dari rumus prevention_check. Tidak commit: dipanggil
    di dalam transaksi aksi yang mengubah bahannya, dengan baris request sudah dikunci.
    Status submitted, cleared, dan canceled tidak pernah disentuh (larangan 9)."""
    if req.status not in PRE_SUBMIT_STATUSES:
        return
    state = await evaluate(db, req)
    req.status = RequestStatus.prevention_check if state.prevention_check_ready else RequestStatus.internal