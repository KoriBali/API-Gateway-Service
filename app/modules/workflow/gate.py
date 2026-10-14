"""Gerbang submit dan status prevention_check. Keduanya dihitung dari data, tidak pernah disimpan
sebagai kolom penanda.

File ini tidak meng-import app.modules.case.repository maupun app.modules.intake, karena
keduanya memanggil apply_prevention_status di transaksinya sendiri."""
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.intake import Request, RequestStatus
from app.database.models.workflow import (
    ChecklistItemStatus,
    EventType,
    NcChecklist,
    NcChecklistItem,
    RequestEvent,
    WorkType,
)
from app.modules.assignment.permissions import WORK_TYPES_OF
from app.modules.case.tables import CASE_MODEL
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

    @property
    def prevention_check_ready(self) -> bool:
        """Syarat 1 sampai 3 status prevention_check: checklist ada, tiap work type punya case,
        setiap case diperiksa di siklus ini. Isi checklist belum dinilai."""
        return self.checklist_id is not None and not self.missing_work_types and not self.unchecked_cases

    @property
    def can_submit(self) -> bool:
        """Gerbang submit: syarat prevention_check ditambah tidak ada item pending.
        Syarat 4 (berkas check_result untuk case manual) menyusul plan file management:
        sebelum itu belum ada deliverable, jadi belum ada case manual."""
        return self.prevention_check_ready and self.pending_items == 0



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
        rows = (await db.execute(
            select(model.id, model.title, checked)
            .where(model.request_id == req.id)
            .order_by(model.created_at, model.id)
        )).all()
        # Syarat 2: keberadaan minimal satu case, bukan perbandingan jumlah (larangan 1).
        if not rows and work_type in WORK_TYPES_OF[req.design_type]:
            state.missing_work_types.append(work_type)
        state.unchecked_cases += [
            UncheckedCase(work_type=work_type, case_id=case_id, title=title)
            for case_id, title, is_checked in rows if not is_checked
        ]
    return state



async def apply_prevention_status(db: AsyncSession, req: Request) -> None:
    """Isi requests.status dari rumus prevention_check. Tidak commit: dipanggil
    di dalam transaksi aksi yang mengubah bahannya, dengan baris request sudah dikunci.
    Status submitted, cleared, dan canceled tidak pernah disentuh (larangan 9)."""
    if req.status not in PRE_SUBMIT_STATUSES:
        return
    state = await evaluate(db, req)
    req.status = RequestStatus.prevention_check if state.prevention_check_ready else RequestStatus.internal