from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.assignment import permissions
from app.modules.assignment.repository import AssignmentRepository, WorkHourRepository
from app.modules.assignment.routers.assignments import assignment_not_found, load_readable_request
from app.modules.assignment.schemas import (
    WorkHourCreate,
    WorkHourRead,
    WorkHourSummaryRead,
    WorkHourUpdate,
    WorkTypeHours,
)

routerWorkHour = APIRouter(prefix="/api/requests", tags=["Request Assignment"])

_WORKER_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")



# ===== Helper =====
def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _ensure_not_future(work_date: date) -> None:
    # Toleransi satu hari: tanggal lokal pengguna (WIB, JST) bisa sudah berganti
    # sementara tanggal UTC server belum.
    if work_date > datetime.now(timezone.utc).date() + timedelta(days=1):
        raise _unprocessable("workDate cannot be in the future")


async def _ensure_round(db: AsyncSession, request_id: str, revision_round_id: str | None) -> None:
    if revision_round_id is not None and not await WorkHourRepository.round_in_request(
        db, request_id, revision_round_id,
    ):
        raise _unprocessable("revisionRoundId does not reference a revision round of this request")


async def _load_assignment(db: AsyncSession, request_id: str, assignment_id: str, actor: CurrentUser):
    await load_readable_request(db, request_id, actor)
    row = await AssignmentRepository.get_in_request(db, request_id, assignment_id)
    if row is None:
        raise assignment_not_found()
    return row


async def _load_own_work_hour(
    db: AsyncSession, request_id: str, assignment_id: str, work_hour_id: str, actor: CurrentUser,
):
    assignment = await _load_assignment(db, request_id, assignment_id, actor)
    permissions.ensure_owns_assignment(actor, assignment)
    row = await WorkHourRepository.get_in_assignment(db, assignment_id, work_hour_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work hour not found")
    return row



# ===== Read =====
@routerWorkHour.get("/{request_id}/work-hours/summary")
async def work_hour_summary(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    await load_readable_request(db, request_id, actor)
    rows = await WorkHourRepository.summary_by_work_type(db, request_id)
    return success_response(
        data=WorkHourSummaryRead(
            total_hours=sum((total for _, total in rows), Decimal("0")),
            by_work_type=[WorkTypeHours(work_type=wt, total_hours=total) for wt, total in rows],
        ),
        message="Work hour summary retrieved",
    )


@routerWorkHour.get("/{request_id}/assignments/{assignment_id}/work-hours")
async def list_work_hours(
    request_id: str,
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    await _load_assignment(db, request_id, assignment_id, actor)
    rows = await WorkHourRepository.list_for_assignment(db, assignment_id)
    return success_response(
        data=[WorkHourRead.model_validate(r) for r in rows],
        message="Work hours retrieved",
    )



# ===== Tulis (hanya pemilik assignment) =====
@routerWorkHour.post("/{request_id}/assignments/{assignment_id}/work-hours")
async def create_work_hour(
    request_id: str,
    assignment_id: str,
    payload: WorkHourCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    assignment = await _load_assignment(db, request_id, assignment_id, actor)
    permissions.ensure_owns_assignment(actor, assignment)
    _ensure_not_future(payload.work_date)
    await _ensure_round(db, request_id, payload.revision_round_id)

    row = await WorkHourRepository.create(db, assignment_id, payload.model_dump())
    return success_response(
        data=WorkHourRead.model_validate(row),
        status_code=status.HTTP_201_CREATED,
        message="Work hour recorded",
    )


@routerWorkHour.patch("/{request_id}/assignments/{assignment_id}/work-hours/{work_hour_id}")
async def update_work_hour(
    request_id: str,
    assignment_id: str,
    work_hour_id: str,
    payload: WorkHourUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    row = await _load_own_work_hour(db, request_id, assignment_id, work_hour_id, actor)
    data = payload.model_dump(exclude_unset=True)
    if "work_date" in data:
        _ensure_not_future(data["work_date"])
    if "revision_round_id" in data:
        await _ensure_round(db, request_id, data["revision_round_id"])

    row = await WorkHourRepository.update(db, row, data)
    return success_response(data=WorkHourRead.model_validate(row), message="Work hour updated")


@routerWorkHour.delete("/{request_id}/assignments/{assignment_id}/work-hours/{work_hour_id}")
async def delete_work_hour(
    request_id: str,
    assignment_id: str,
    work_hour_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    row = await _load_own_work_hour(db, request_id, assignment_id, work_hour_id, actor)
    await WorkHourRepository.delete(db, row)
    return success_response(data={"deleted": True}, message="Work hour deleted")