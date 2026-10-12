from fastapi import HTTPException, status

from app.core.security import CurrentUser
from app.database.models.intake import Request



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



def can_read_request(actor: CurrentUser, request: Request) -> bool:
    """Read-scoping request (dipakai router intake & calculation).
    superadmin: semua; admin_department: hanya departemen penanggung jawab-nya;
    selain itu: hanya record miliknya."""
    if actor.role == "superadmin":
        return True
    if actor.role == "admin_department":
        return actor.department_id is not None and \
            request.responsible_department_id == actor.department_id
    return request.created_by_user_id == actor.id