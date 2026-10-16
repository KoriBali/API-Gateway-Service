from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.database.models.intake import Request, RequestStatus
from app.database.models.workflow import (
    AssignmentStatus,
    CheckResult,
    EventType,
    FileRole,
    FileVersion,
    LifecycleStatus,
    RequestAssignment,
    RequestEvent,
    RequestFile,
    RevisionOrigin,
    RevisionRound,
    WorkType,
)
from app.modules.workflow.repository import RequestEventRepository
from app.modules.workflow.gate import apply_prevention_status
from app.modules.case.tables import CASE_FILE_FK, CASE_MODEL, ROUND_SCOPE



@dataclass
class CheckState:
    """Peristiwa ready_for_check dan check terbaru satu case"""
    ready_event: RequestEvent | None = None
    check_event: RequestEvent | None = None
    
    @property
    def in_check_queue(self) -> bool:
        """Antrean pemriksaan ready_for_check terbaru tanpa check sesudahnya"""
        if self.ready_event is None:
            return False
        return self.check_event is None or self.check_event.occurred_at < self.ready_event.occurred_at
    
    
@dataclass
class DeliverableState:
    """Deliverable satu case: ada tidaknya versi aktif, dan waktu unggah versi terbaru."""
    has_active: bool = False
    last_uploaded_at: datetime | None = None

    def newer_than(self, moment: datetime | None) -> bool:
        """Ada versi yang lahir sesudah moment (siap dicek atau diperiksa terakhir)."""
        return moment is not None and self.last_uploaded_at is not None and self.last_uploaded_at > moment
    


# ===== Case lintas Work Type =====
class CaseRepository:
    @staticmethod
    async def get_in_request(db:AsyncSession, work_type: WorkType, request_id: str,
    case_id: str):
        model = CASE_MODEL[work_type]
        stmt = (
            select(model)
            .where(model.id == case_id, model.request_id == request_id)
            .options(selectinload(model.owner_user))
        )
        return (await db.execute(stmt)).scalar_one_or_none()
    
    @staticmethod
    async def list_in_request(db: AsyncSession, request_id: str) -> list[tuple[WorkType, object]]:
        """Seluruh case satu request, calculation dulu lalu drawing, urut waktu dibuat"""
        rows = []
        for work_type, model in CASE_MODEL.items():
            stmt = (
                select(model)
                .where(model.request_id == request_id)
                .options(selectinload(model.owner_user))
                .order_by(model.created_at, model.id)
            )
            rows += [(work_type, case) for case in (await db.execute(stmt)).scalars().all()]
        return rows
        
    @staticmethod
    async def check_states(db: AsyncSession, request_id: str) -> dict[tuple[WorkType, str], CheckState]:
        """Keadaan permeriksaan tiap case di request ini, kunci (work_type, case_id)"""
        stmt = (
            select(RequestEvent)
            .where(
                RequestEvent.request_id == request_id,
                RequestEvent.event_type.in_((EventType.ready_for_check, EventType.check)),
            )
            .order_by(RequestEvent.occurred_at, RequestEvent.id)
        )
        states: dict[tuple[WorkType, str], CheckState] = {}
        for event in (await db.execute(stmt)).scalars().all():
            state = states.setdefault((event.work_type, event.case_id), CheckState())
            if event.event_type == EventType.ready_for_check:
                state.ready_event = event
            else:
                state.check_event = event
        return states
    
    @staticmethod
    async def deliverable_states(
        db: AsyncSession, request_ids: list[str],
    ) -> dict[tuple[WorkType, str], DeliverableState]:
        """Keadaan deliverable tiap case di request-request ini, kunci (work_type, case_id).
        Sumber keterangan "ada versi baru sesudah siap dicek atau sesudah diperiksa"""
        states: dict[tuple[WorkType, str], DeliverableState] = {}
        if not request_ids:
            return states
        for work_type, column in CASE_FILE_FK.items():
            stmt = (
                select(
                    column,
                    func.bool_or(FileVersion.lifecycle_status == LifecycleStatus.active),
                    func.max(FileVersion.uploaded_at),
                )
                .join(FileVersion, FileVersion.request_file_id == RequestFile.id)
                .where(
                    RequestFile.request_id.in_(request_ids),
                    RequestFile.file_role == FileRole.deliverable,
                    column.is_not(None),
                )
                .group_by(column)
            )
            for case_id, has_active, last_uploaded_at in (await db.execute(stmt)).all():
                states[(work_type, case_id)] = DeliverableState(bool(has_active), last_uploaded_at)
        return states
        
    @staticmethod
    async def get_check_state(db: AsyncSession, request_id: str, work_type: WorkType, case_id: str) -> CheckState:
        return (await CaseRepository.check_states(db, request_id)).get((work_type, case_id), CheckState())
    
    @staticmethod
    async def cycle_start(db: AsyncSession, request_id: str) -> datetime | None:
        """Batas awal submit berjalan feedback terakhir, atau kosong"""
        return (await RequestEventRepository.current_cycle(db, request_id))[1]
        
    @staticmethod
    async def active_assignments(db: AsyncSession, request_id: str) -> set[tuple[str, WorkType]]:
        """Pasangan yang punya assigment aktif di request ini"""
        stmt = select(RequestAssignment.assignee_user_id, RequestAssignment.work_type).where(
            RequestAssignment.request_id == request_id,
            RequestAssignment.assignment_status == AssignmentStatus.active
        )
        return {(row[0], row[1]) for row in (await db.execute(stmt)).all()}
    
    @staticmethod
    async def has_check(db:AsyncSession, work_type: WorkType, case_id: str) -> bool:
        stmt = select(exists().where(
            RequestEvent.case_id == case_id,
            RequestEvent.work_type == work_type,
            RequestEvent.event_type == EventType.check
        ))
        return bool(await db.scalar(stmt))
    
    @staticmethod
    def without_active_owner_clause():
        """Kondisi SQL 'request ini punya case yang ownernya tidak punay assigment aktif di work type case itu'. berkolerasi ke request.id, dipakai di WHERE queary daftar request"""
        def one(model, work_type: WorkType):
            return exists().where(
                model.request_id == Request.id,
                ~exists().where(
                    RequestAssignment.request_id == model.request_id,
                    RequestAssignment.assignee_user_id == model.owner_user_id,
                    RequestAssignment.work_type == work_type,
                    RequestAssignment.assignment_status == AssignmentStatus.active,
                )
            )
        return or_(*(one(model, work_type) for work_type, model in CASE_MODEL.items()))
    
    @staticmethod
    async def check_queue(
        db: AsyncSession, *, department_id: str | None, limit: int, offset: int) -> tuple[list[tuple[RequestEvent, Request, object]], int]:
        """Antrean pemeriksaan lintas request: ready_for_check terbaru tiap case yang belum
        disusul check, pada case yang masih ada, di request yang belum dibatalkan. department_id none = semua department (superadmin)
        """
        ready = RequestEvent
        later = aliased(RequestEvent)
        stmt = (
            select(ready, Request)
            .join(Request, Request.id == ready.request_id)
            .where(
                ready.event_type == EventType.ready_for_check,
                ~exists().where(
                    later.case_id == ready.case_id,
                    later.work_type == ready.work_type,
                    later.event_type.in_((EventType.ready_for_check, EventType.check)),
                    later.occurred_at > ready.occurred_at
                ),
                or_(*(
                    and_(ready.work_type == work_type, exists().where(model.id == ready.case_id)) for work_type, model in CASE_MODEL.items()
                )),
                Request.status != RequestStatus.canceled
            )
        )
        if department_id is not None:
            stmt = stmt.where(Request.responsible_department_id == department_id)
            
        total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
        stmt = stmt.order_by(ready.occurred_at, ready.id).limit(limit).offset(offset)
        pairs = [(row[0], row[1]) for row in (await db.execute(stmt)).all()]
        
        # Muat case-nya per work type, satu query per table
        cases = {}
        for work_type, model in CASE_MODEL.items():
            ids = [e.case_id for e, _ in pairs if e.work_type == work_type]
            if ids:
                found = await db.execute(
                    select(model).where(model.id.in_(ids)).options(selectinload(model.owner_user))
                )
                cases.update({(work_type, c.id): c for c in found.scalars().all()})
        return [(e, req, cases[(e.work_type, e.case_id)]) for e, req, in pairs], int(total or 0)
    
    @staticmethod
    async def record_event(
        db:AsyncSession,
        req: Request,
        case,
        *,
        work_type: WorkType,
        actor_id: str,
        event_type: EventType,
        check_result: CheckResult | None = None,
        payload: dict | None = None,
        round_note: str | None = None,
        new_owner_user_id: str | None = None
    ) -> tuple[RequestEvent, RevisionRound | None]:
        """
        Satu transaksi: catat peristiwa tingkat case, buka putaran internal bila check has_findings, ganti woner bila ownership_transfer.
        pemanggil wajib sudah mengunci req(get_for_update). request.status tidak berubah oleh peristiwa tingkat case
        """
        event = RequestEvent(
            request_id = req.id,
             actor_user_id = actor_id,
             event_type = event_type,
             case_id = case.id,
             work_type = work_type,
             check_result = check_result, 
             payload = payload
        )
        db.add(event)
        await db.flush()
        
        revision_round = None
        if check_result == CheckResult.has_findings:
            revision_round = RevisionRound(
                request_id = req.id,
                check_event_id = event.id,
                round_number = await RequestEventRepository.next_round_number(db, req.id),
                work_scope = ROUND_SCOPE[work_type],
                origin = RevisionOrigin.internal_correction,
                trigger_note = round_note
            )
            db.add(revision_round)
            
        if new_owner_user_id is not None:
            case.owner_user_id = new_owner_user_id

        if event_type == EventType.check:
            # Check bisa melengkapi syarat prevention_check, di transaksi yang sama.
            await db.flush()
            await apply_prevention_status(db, req)


            
        await db.commit()
        await db.refresh(event)
        
        if revision_round is not None:
            await db.refresh(revision_round)
        return event, revision_round
    