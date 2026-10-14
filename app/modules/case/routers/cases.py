from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake import permissions as intake_permissions
from app.modules.workflow.repository import RequestEventRepository
from app.modules.workflow.schemas import RequestEventRead, RequestEventResult, RevisionRoundRead
from app.modules.case import permissions
from app.modules.case.repository import CaseRepository
from app.modules.case.schemas import CaseSummaryRead, CheckCreate, OwnershipTransferCreate
from app.database.models.workflow import EventType, WorkType

routerCase = APIRouter(prefix="/api/requests", tags=["Case Workflow"])

# Pihak Koribali saja. yoshimoto_reviewer tidak melihat pekerjaan di dalam department
_READ_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")
# Menandai siap dicek dan mengalihkan kepemilikan: owner atau admin_department (dicek di handler).
_WORKER_ROLE = require_roles("admin_department", "drafter_checker", "drafter")
# Memberi check: drafter_checker dan admin_department
_CHECKER_ROLE = require_roles("admin_department", "drafter_checker")



# ===== Helper =====
async def _load_for_case_event(
    db: AsyncSession, request_id: str, work_type: WorkType, case_id: str, actor: CurrentUser,
):
    """Kunci baris request dulu, baru baca case: peristiwa case di request yang sama berjalan
    bergiliran (nomor putaran internal, pengalihan ganda, hapus case vs check)."""
    req = await RequestEventRepository.get_for_update(db, request_id)
    if req is None or not await intake_permissions.is_readable(db, actor, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    case = await CaseRepository.get_in_request(db, work_type, request_id, case_id)
    if case is None:
        raise permissions.case_not_found()
    return req, case


def _result(req, event, revision_round=None, message: str = ""):
    return success_response(
        data=RequestEventResult(
            status=req.status,
            event=RequestEventRead.model_validate(event),
            revision_round=RevisionRoundRead.model_validate(revision_round) if revision_round else None,
        ),
        status_code=status.HTTP_201_CREATED,
        message=message,
    )



# ===== Ringkasan case =====
@routerCase.get("/{request_id}/cases")
async def list_cases(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    """Seluruh case request (calculation dan drawing) beserta keadaan pemeriksaannya."""
    await permissions.load_readable_request(db, request_id, actor)
    cases = await CaseRepository.list_in_request(db, request_id)
    states = await CaseRepository.check_states(db, request_id)
    active = await CaseRepository.active_assignments(db, request_id)
    cycle_start = await CaseRepository.cycle_start(db, request_id)

    items = []
    for work_type, case in cases:
        state = states.get((work_type, case.id))
        ready = state.ready_event if state else None
        check = state.check_event if state else None
        items.append(CaseSummaryRead(
            id=case.id,
            work_type=work_type,
            title=case.title,
            case_label=case.case_label,
            pole_kind=case.pole_kind,
            created_by_user_id=case.created_by_user_id,
            owner_user_id=case.owner_user_id,
            owner=case.owner_user,
            owner_has_active_assignment=(case.owner_user_id, work_type) in active,
            ready_for_check_at=ready.occurred_at if ready else None,
            ready_for_check_by_user_id=ready.actor_user_id if ready else None,
            last_check_at=check.occurred_at if check else None,
            last_check_result=check.check_result if check else None,
            last_checked_by_user_id=check.actor_user_id if check else None,
            in_check_queue=bool(state and state.in_check_queue),
            checked_in_current_cycle=check is not None and (cycle_start is None or check.occurred_at > cycle_start),
            created_at=case.created_at,
            updated_at=case.updated_at,
        ))
    return success_response(data=items, message="Cases retrieved")



# ===== Peristiwa tingkat case =====
@routerCase.post("/{request_id}/cases/{work_type}/{case_id}/ready-for-check")
async def mark_ready_for_check(
    request_id: str,
    work_type: WorkType,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    req, case = await _load_for_case_event(db, request_id, work_type, case_id, actor)
    permissions.ensure_owner_or_admin(actor, case, "mark it ready for check")
    state = await CaseRepository.get_check_state(db, request_id, work_type, case_id)
    if state.in_check_queue:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case is already waiting for check")

    event, _ = await CaseRepository.record_event(
        db, req, case,
        work_type=work_type,
        actor_id=actor.id,
        event_type=EventType.ready_for_check,
    )
    return _result(req, event, message="Case marked ready for check")


@routerCase.post("/{request_id}/cases/{work_type}/{case_id}/check")
async def check_case(
    request_id: str,
    work_type: WorkType,
    case_id: str,
    payload: CheckCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_CHECKER_ROLE),
):
    # Tidak menuntut ready_for_check lebih dulu: sistem mencatat, tidak memaksa urutan
    # Pemeriksa sama dengan owner juga tidak ditolak, hanya terbaca di ringkasan
    req, case = await _load_for_case_event(db, request_id, work_type, case_id, actor)
    event, revision_round = await CaseRepository.record_event(
        db, req, case,
        work_type=work_type,
        actor_id=actor.id,
        event_type=EventType.check,
        check_result=payload.check_result,
        payload={"note": payload.note} if payload.note else None,
        round_note=payload.note,
    )
    return _result(req, event, revision_round, message="Case checked")


@routerCase.post("/{request_id}/cases/{work_type}/{case_id}/transfer-ownership")
async def transfer_ownership(
    request_id: str,
    work_type: WorkType,
    case_id: str,
    payload: OwnershipTransferCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    req, case = await _load_for_case_event(db, request_id, work_type, case_id, actor)
    permissions.ensure_owner_or_admin(actor, case, "transfer its ownership")
    await permissions.ensure_transfer_target(db, req, case, work_type, payload.new_owner_user_id)

    event, _ = await CaseRepository.record_event(
        db, req, case,
        work_type=work_type,
        actor_id=actor.id,
        event_type=EventType.ownership_transfer,
        payload={
            "previousOwnerUserId": case.owner_user_id,
            "newOwnerUserId": payload.new_owner_user_id,
        },
        new_owner_user_id=payload.new_owner_user_id,
    )
    return _result(req, event, message="Case ownership transferred")