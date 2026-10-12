from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.database.models.intake import Request
from app.modules.workflow.repository import RequestEventRepository



def _forbidden(detail: str = "You do not have permission to perform this action"):
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)



def ensure_can_manage_request(actor: CurrentUser, request: Request) -> None:
    """
        Boleh update/delete:
        - superadmin (semua)
        - admin_department di departemen penanggung jawab request
        - pembuat request itu sendiri (record miliknya)
    """
    # TODO(workflow): izin lengkap per peran menyusul di plan workflow.
    if actor.role == "superadmin":
        return
    if actor.role == "admin_department" and actor.department_id is not None \
            and request.responsible_department_id == actor.department_id:
        return
    if request.created_by_user_id == actor.id:
        return
    raise _forbidden()



def can_read_request(actor: CurrentUser, request: Request, *, ever_submitted: bool = False) -> bool:
    """Read-scoping request (dipakai router intake, calculation, workflow).
    superadmin: semua; admin_department: hanya departemen penanggung jawab-nya;
    yoshimoto_reviewer: request yang pernah di-submit, lintas department (V6, V7);
    selain itu: hanya record miliknya.
    ever_submitted hanya dibaca untuk yoshimoto_reviewer; pakai is_readable bila perlu menghitungnya."""
    if actor.role == "superadmin":
        return True
    if actor.role == "admin_department":
        return actor.department_id is not None and \
            request.responsible_department_id == actor.department_id
    if actor.role == "yoshimoto_reviewer":
        return ever_submitted
    return request.created_by_user_id == actor.id



async def is_readable(db: AsyncSession, actor: CurrentUser, request: Request) -> bool:
    """can_read_request + query 'pernah di-submit' khusus yoshimoto_reviewer."""
    ever_submitted = (
        actor.role == "yoshimoto_reviewer"
        and await RequestEventRepository.has_submit(db, request.id)
    )
    return can_read_request(actor, request, ever_submitted=ever_submitted)
