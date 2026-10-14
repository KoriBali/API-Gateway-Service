from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.database.models.intake import Request
from app.modules.workflow.repository import RequestEventRepository
from app.modules.assignment.repository import AssignmentRepository



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



def can_read_request(
    actor: CurrentUser, request: Request, *, ever_submitted: bool = False, assigned: bool = False,
) -> bool:
    """Read-scoping request (dipakai router intake, calculation, drawing, case, workflow, assignment).
    superadmin: semua; admin_department: hanya departemen penanggung jawab-nya;
    yoshimoto_reviewer: request yang pernah di-submit, lintas department;
    drafter_checker: seluruh request departemennya, karena pemeriksaan tidak memerlukan
    assignment; selain itu: record miliknya, atau request tempat ia pernah punya assignment.
    ever_submitted dan assigned dihitung is_readable; pemanggil sinkron cukup memakai default."""
    if actor.role == "superadmin":
        return True
    if actor.role == "admin_department":
        return actor.department_id is not None and \
            request.responsible_department_id == actor.department_id
    if actor.role == "yoshimoto_reviewer":
        return ever_submitted
    if actor.role == "drafter_checker" and actor.department_id is not None \
            and request.responsible_department_id == actor.department_id:
        return True
    return request.created_by_user_id == actor.id or assigned




async def is_readable(db: AsyncSession, actor: CurrentUser, request: Request) -> bool:
    """can_read_request + query yang hanya perlu untuk peran tertentu:
    'pernah di-submit' untuk yoshimoto_reviewer, 'pernah di-assign' untuk pengerja yang bukan pembuat."""
    ever_submitted = (
        actor.role == "yoshimoto_reviewer"
        and await RequestEventRepository.has_submit(db, request.id)
    )
    assigned = (
        actor.role in ("drafter", "drafter_checker")
        and request.created_by_user_id != actor.id
        and await AssignmentRepository.has_any(db, request.id, actor.id)
    )
    return can_read_request(actor, request, ever_submitted=ever_submitted, assigned=assigned)