from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake import permissions as intake_permissions
from app.modules.intake.repository import RequestRepository
from app.modules.assignment import permissions
from app.modules.assignment.repository import AssignmentRepository, DuplicateActiveAssignment
from app.database.models.workflow import AssignmentStatus
from app.modules.assignment.schemas import AssignmentCreate, AssignmentRead

routerAssignment = APIRouter(prefix="/api/requests", tags=["Request Assignment"])

# Pihak Koribali saja. yoshimoto_reviewer tidak membaca maupun mengatur pengerja (V6).
_WORKER_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")



# ===== Helper =====
async def load_readable_request(db: AsyncSession, request_id: str, actor: CurrentUser):
    req = await RequestRepository.get_by_id(db, request_id)
    if req is None or not await intake_permissions.is_readable(db, actor, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return req


def assignment_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")


def _read(row, total_hours=None) -> AssignmentRead:
    data = AssignmentRead.model_validate(row)
    data.total_hours = total_hours
    return data



# ===== Read =====
@routerAssignment.get("/{request_id}/assignments")
async def list_assignments(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    await load_readable_request(db, request_id, actor)
    rows = await AssignmentRepository.list_with_hours(db, request_id)
    return success_response(
        data=[_read(row, total) for row, total in rows],
        message="Assignments retrieved",
    )



# ===== Tambah =====
@routerAssignment.post("/{request_id}/assignments")
async def add_assignment(
    request_id: str,
    payload: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    req = await load_readable_request(db, request_id, actor)
    await permissions.ensure_can_add(db, actor, req)
    await permissions.ensure_assignable(
        db,
        department_id=req.responsible_department_id,
        design_type=req.design_type,
        assignee_user_id=payload.assignee_user_id,
        work_type=payload.work_type,
    )

    conflict = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="This user already has an active assignment for this workType on the request",
    )
    if await AssignmentRepository.has_active(db, req.id, payload.assignee_user_id, payload.work_type):
        raise conflict
    try:
        row = await AssignmentRepository.create(
            db,
            request_id=req.id,
            assignee_user_id=payload.assignee_user_id,
            work_type=payload.work_type,
            assigned_by_user_id=actor.id,
        )
    except DuplicateActiveAssignment:
        raise conflict
    return success_response(
        data=_read(row),
        status_code=status.HTTP_201_CREATED,
        message="Assignment added",
    )



# ===== Lepas =====
@routerAssignment.post("/{request_id}/assignments/{assignment_id}/release")
async def release_assignment(
    request_id: str,
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    await load_readable_request(db, request_id, actor)
    # Kunci baris: dua pelepasan bersamaan tidak saling menimpa released_by.
    row = await AssignmentRepository.get_in_request(db, request_id, assignment_id, for_update=True)
    if row is None:
        raise assignment_not_found()
    permissions.ensure_can_release(actor, row)
    if row.assignment_status == AssignmentStatus.released:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assignment is already released")

    row = await AssignmentRepository.release(db, row, released_by_user_id=actor.id)
    return success_response(data=_read(row), message="Assignment released")