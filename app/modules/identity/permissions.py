from fastapi import HTTPException, status

from app.core.security import CurrentUser
from app.database.models.identity import User



def _role_str(role) -> str:
    return role.value if hasattr(role, "value") else str(role)



def _forbidden(detail:str = "You do not have permission to perform this action"):
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)



_DEPARTMENT_MANAGED_ROLES = ("drafter", "drafter_checker")



def ensure_can_create_user(actor: CurrentUser, target_role, target_department_id: str | None) -> None:
    # Check apakah current user dapat membuat user di department ini?
    if actor.role == "superadmin":
        return
    if actor.role == "admin_department":
        if _role_str(target_role) not in _DEPARTMENT_MANAGED_ROLES:
            raise _forbidden("Admin Department can only create drafter or drafter_checker accounts")
        if actor.department_id is None or target_department_id != actor.department_id:
            raise _forbidden("Admin Department can only create users in their own department")
        return
    raise _forbidden()



def ensure_can_manage_user(actor: CurrentUser, target_user: User) -> None:
    # Check apakah current user dapat mereset/menonaktifkan target user?
    if actor.role == "superadmin":
        return
    if actor.role == "admin_department":
        if _role_str(target_user.role) not in _DEPARTMENT_MANAGED_ROLES:
            raise _forbidden()
        if actor.department_id is None or target_user.department_id != actor.department_id:
            raise _forbidden()
        return
    raise _forbidden()



def ensure_can_change_role_or_department(actor: CurrentUser, new_role, department_changed: bool) -> None:
    """superadmin: bebas. admin_department: hanya menukar drafter <-> drafter_checker,
    tanpa memindahkan department (V5). Target sudah lolos ensure_can_manage_user."""
    if actor.role == "superadmin":
        return
    if actor.role == "admin_department":
        if department_changed:
            raise _forbidden("Only superadmin can change a user's department")
        if new_role is not None and _role_str(new_role) not in _DEPARTMENT_MANAGED_ROLES:
            raise _forbidden("Admin Department can only switch roles between drafter and drafter_checker")
        return
    raise _forbidden("Only superadmin can change role or department")
