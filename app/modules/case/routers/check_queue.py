from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.case.repository import CaseRepository, DeliverableState
from app.modules.case.schemas import CheckQueueItemRead

routerCheckQueue = APIRouter(prefix="/api/check-queue", tags=["Case Workflow"])

# Yang boleh memberi check, ditambah superadmin untuk membaca (S-1).
_QUEUE_ROLE = require_roles("superadmin", "admin_department", "drafter_checker")



@routerCheckQueue.get("")
async def list_check_queue(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_QUEUE_ROLE),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Case yang menunggu pemeriksaan di department actor, yang paling lama menunggu di atas."""
    if actor.role != "superadmin" and actor.department_id is None:
        rows, total = [], 0
    else:
        rows, total = await CaseRepository.check_queue(
            db,
            department_id=None if actor.role == "superadmin" else actor.department_id,
            limit=limit,
            offset=offset,
        )
    deliverables = await CaseRepository.deliverable_states(db, list({req.id for _, req, _ in rows}))
    items = [
        CheckQueueItemRead(
            request_id=req.id,
            request_no=req.request_no,
            request_subject=req.subject,
            request_status=req.status,
            work_type=event.work_type,
            case_id=case.id,
            title=case.title,
            case_label=case.case_label,
            owner=case.owner_user,
            ready_for_check_at=event.occurred_at,
            ready_for_check_by_user_id=event.actor_user_id,
            new_version_after_ready_for_check=deliverables.get(
                (event.work_type, case.id), DeliverableState()
            ).newer_than(event.occurred_at),
        )
        for event, req, case in rows
    ]
    return success_response(
        data={"items": items, "total": total, "limit": limit, "offset": offset},
        message="Check queue retrieved",
    )