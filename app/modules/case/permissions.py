from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.database.models.intake import Request
from app.database.models.workflow import WorkType
from app.modules.assignment.permissions import WORK_TYPES_OF
from app.modules.assignment.repository import AssignmentRepository
from app.modules.intake import permissions as intake_permissions
from app.modules.intake.repository import RequestRepository



def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def case_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")



async def load_readable_request(db: AsyncSession, request_id: str, actor: CurrentUser) -> Request:
    """404 bila request tidak ada atau tidak boleh dibaca actor."""
    req = await RequestRepository.get_by_id(db, request_id)
    if req is None or not await intake_permissions.is_readable(db, actor, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return req



async def ensure_can_create(db: AsyncSession, actor: CurrentUser, request: Request, work_type: WorkType) -> None:
    """Pengerja membuat case sendiri: actor wajib punya
    assignment aktif di work type itu. Pembuat case menjadi owner pertamanya."""
    if work_type not in WORK_TYPES_OF[request.design_type]:
        raise _unprocessable(
            f"workType '{work_type.value}' is not part of the request designType '{request.design_type.value}'"
        )
    if not await AssignmentRepository.has_active(db, request.id, actor.id, work_type):
        raise _forbidden(f"Only a user with an active {work_type.value} assignment on this request can create the case")



def ensure_owner(actor: CurrentUser, case) -> None:
    """Hanya owner yang mengubah isi case"""
    if case.owner_user_id != actor.id:
        raise _forbidden("Only the case owner can change this case")



def ensure_owner_or_admin(actor: CurrentUser, case, action: str) -> None:
    """Menandai siap dicek, mengalihkan kepemilikan, dan menghapus case: owner atau admin_department.
    Pemanggil sudah memastikan request terbaca, jadi admin_department di sini pasti
    admin department penanggung jawab."""
    if actor.role == "admin_department" or case.owner_user_id == actor.id:
        return
    raise _forbidden(f"Only the case owner or admin_department can {action}")



async def ensure_transfer_target(
    db: AsyncSession, request: Request, case, work_type: WorkType, new_owner_user_id: str,
) -> None:
    """Penerima wajib punya assignment aktif di work type case itu"""
    if new_owner_user_id == case.owner_user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This user already owns the case")
    if not await AssignmentRepository.has_active(db, request.id, new_owner_user_id, work_type):
        raise _unprocessable(
            f"newOwnerUserId must have an active {work_type.value} assignment on this request"
        )