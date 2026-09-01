from fastapi import HTTPException, status

from app.core.security import CurrentUser
from app.database.models.identity import Role, User, Request



def _role_str(role) -> str:
    return role.value if hasattr(role, "value") else str(role)



def _forbidden(detail:str = "You do not have permission to perform this action"):
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)



def ensure_can_create_user(actor: CurrentUser, target_role, target_department_id: str | None) -> None:
    # Check apakah current user dapat membuat user di department ini?
    if actor.role == "superadmin":
        return
    if actor.role == "admin":
        if _role_str(target_role) != "drafter":
            raise _forbidden("Admin can only create drafter accounts")
        if actor.department_id is None or target_department_id != actor.department_id:
            raise _forbidden("Admin can only create users in their own department")
        return
    raise _forbidden()



def ensure_can_manage_user(actor: CurrentUser, target_user: User) -> None:
    # Check apakah current user dapat mereset/menonaktifkan target user?
    if actor.role == "superadmin":
        return
    if actor.role == "admin":
        if _role_str(target_user.role) != "drafter":
            raise _forbidden()
        if actor.department_id is None or target_user.department_id != actor.department_id:
            raise _forbidden()
        return
    raise _forbidden()



def ensure_can_change_role_or_department(actor: CurrentUser) -> None:
    # Only Superadmin
    if actor.role != "superadmin":
        raise _forbidden("Only superadmin can change role or department")



def ensure_can_manage_request(actor: CurrentUser, request: Request) -> None:
    """
    Boleh update/delete:
    - superadmin (semua)
    - admin di departemen penanggung jawab request
    - pembuat request itu sendiri (record miliknya)
    """
    if actor.role == "superadmin":
        return
    if actor.role == "admin" and actor.department_id is not None \
            and request.responsible_department_id == actor.department_id:
        return
    if request.created_by_user_id == actor.id:
        return
    raise _forbidden()    



def ensure_can_submit_request(actor: CurrentUser, request: Request) -> None:
    """Hanya PEMBUAT yang boleh submit (draft -> submitted)."""
    if request.created_by_user_id == actor.id:
        return
    raise _forbidden("Only the request creator can submit this request")