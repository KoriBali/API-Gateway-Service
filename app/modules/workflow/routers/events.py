from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake import permissions as intake_permissions
from app.modules.intake.repository import RequestRepository
from app.modules.workflow import permissions
from app.modules.workflow.repository import RequestEventRepository
from app.database.models.workflow import EventType, RevisionOrigin
from app.modules.workflow.schemas import (
    CancelCreate,
    FeedbackCreate,
    RequestEventRead,
    RequestEventResult,
    RevisionRoundRead,
)

routerRequestEvent = APIRouter(prefix="/api/requests", tags=["Request Workflow"])

# Baca riwayat: semua peran, di-scope oleh is_readable.
_READ_ROLE = require_roles(
    "superadmin", "admin_department", "drafter_checker", "drafter", "yoshimoto_reviewer"
)
# Membuka gerbang submit hanya admin_department.
_ADMIN_DEPARTMENT = require_roles("admin_department")
# Empat aksi pihak Yoshimoto (V6, V8).
_REVIEWER = require_roles("yoshimoto_reviewer")



# ===== Helper =====
def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")


async def _load_readable(db: AsyncSession, request_id: str, actor: CurrentUser):
    req = await RequestRepository.get_by_id(db, request_id)
    if req is None or not await intake_permissions.is_readable(db, actor, req):
        raise _not_found()
    return req


async def _load_for_event(db: AsyncSession, request_id: str, actor: CurrentUser, event_type: EventType):
    """Kunci baris request, lalu cek berurutan: terlihat (404), status sah (409)."""
    req = await RequestEventRepository.get_for_update(db, request_id)
    if req is None or not await intake_permissions.is_readable(db, actor, req):
        raise _not_found()
    permissions.ensure_status_allows(req, event_type)
    return req


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



# ===== Read =====
@routerRequestEvent.get("/{request_id}/events")
async def list_request_events(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    await _load_readable(db, request_id, actor)
    rows = await RequestEventRepository.list_events(
        db, request_id, request_level_only=actor.role == "yoshimoto_reviewer"
    )
    return success_response(
        data=[RequestEventRead.model_validate(e) for e in rows],
        message="Request events retrieved",
    )


@routerRequestEvent.get("/{request_id}/revision-rounds")
async def list_revision_rounds(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    await _load_readable(db, request_id, actor)
    rows = await RequestEventRepository.list_rounds(
        db, request_id,
        origin=RevisionOrigin.japan_correction if actor.role == "yoshimoto_reviewer" else None
    )
    return success_response(
        data=[RevisionRoundRead.model_validate(r) for r in rows],
        message="Revision rounds retrieved",
    )



# ===== Aksi admin_department =====
@routerRequestEvent.post("/{request_id}/submit")
async def submit_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ADMIN_DEPARTMENT),
):
    # admin_department hanya bisa membaca request departemennya, jadi is_readable
    # sekaligus menjaga batas department.
    req = await _load_for_event(db, request_id, actor, EventType.submit)
    event, _ = await RequestEventRepository.record(
        db, req,
        actor_id=actor.id,
        event_type=EventType.submit,
        new_status=permissions.RESULT_STATUS[EventType.submit],
    )
    return _result(req, event, message="Request submitted")



# ===== Aksi yoshimoto_reviewer =====
@routerRequestEvent.post("/{request_id}/feedback")
async def give_feedback(
    request_id: str,
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_REVIEWER),
):
    req = await _load_for_event(db, request_id, actor, EventType.feedback)
    work_scope = permissions.resolve_work_scope(req, payload.work_scope)
    event, revision_round = await RequestEventRepository.record(
        db, req,
        actor_id=actor.id,
        event_type=EventType.feedback,
        new_status=permissions.RESULT_STATUS[EventType.feedback],
        feedback_note=payload.note,
        work_scope=work_scope,
    )
    return _result(req, event, revision_round, message="Feedback recorded")


@routerRequestEvent.post("/{request_id}/clear")
async def clear_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_REVIEWER),
):
    req = await _load_for_event(db, request_id, actor, EventType.clear)
    event, _ = await RequestEventRepository.record(
        db, req,
        actor_id=actor.id,
        event_type=EventType.clear,
        new_status=permissions.RESULT_STATUS[EventType.clear],
    )
    return _result(req, event, message="Request cleared")


@routerRequestEvent.post("/{request_id}/reopen")
async def reopen_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_REVIEWER),
):
    req = await _load_for_event(db, request_id, actor, EventType.reopen)
    event, _ = await RequestEventRepository.record(
        db, req,
        actor_id=actor.id,
        event_type=EventType.reopen,
        new_status=permissions.RESULT_STATUS[EventType.reopen],
    )
    return _result(req, event, message="Request reopened")


@routerRequestEvent.post("/{request_id}/cancel")
async def cancel_request(
    request_id: str,
    payload: CancelCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_REVIEWER),
):
    req = await _load_for_event(db, request_id, actor, EventType.cancel)
    event, _ = await RequestEventRepository.record(
        db, req,
        actor_id=actor.id,
        event_type=EventType.cancel,
        new_status=permissions.RESULT_STATUS[EventType.cancel],
        payload={"reason": payload.reason},
    )
    return _result(req, event, message="Request canceled")