from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.database.models.identity import UserRole
from app.database.models.intake import DesignType, Request
from app.database.models.workflow import RequestAssignment, WorkType
from app.modules.assignment.repository import AssignmentRepository
from app.modules.identity.repository import DepartmentRepository


# Work type yang tercakup tiap design_type request.
WORK_TYPES_OF: dict[DesignType, tuple[WorkType, ...]] = {
    DesignType.calculation: (WorkType.calculation,),
    DesignType.drawing: (WorkType.drawing,),
    DesignType.drawing_calculation: (WorkType.calculation, WorkType.drawing),
}

# Peran yang boleh menjadi pengerja. reviewer dan superadmin tidak pernah mengerjakan request.
ASSIGNABLE_ROLES = frozenset({UserRole.drafter, UserRole.drafter_checker, UserRole.admin_department})

# Peran pengerja yang ikut di-assign otomatis saat membuat request.
SELF_ASSIGN_ROLES = frozenset({"drafter", "drafter_checker"})



def _forbidden(detail: str = "You do not have permission to perform this action"):
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)



async def ensure_assignable(
    db: AsyncSession,
    *,
    department_id: str,
    design_type: DesignType,
    assignee_user_id: str,
    work_type: WorkType,
) -> None:
    """Syarat assignee sah (keputusan D). Dipakai saat create request dan saat menambah assignment.
    department_id dan design_type milik request, dioper terpisah karena saat create request belum ada."""
    if work_type not in WORK_TYPES_OF[design_type]:
        raise _unprocessable(f"workType '{work_type.value}' is not part of the request designType '{design_type.value}'")
    user = await AssignmentRepository.get_user(db, assignee_user_id)
    if user is None:
        raise _unprocessable("assigneeUserId does not reference an existing user")
    if not user.is_active:
        raise _unprocessable("assigneeUserId references an inactive user")
    if user.role not in ASSIGNABLE_ROLES:
        raise _unprocessable(f"A user with role '{user.role.value}' cannot be assigned to a request")
    if user.department_id != department_id:
        raise _unprocessable("assigneeUserId must belong to the request's responsible department")
    
    
    
async def resolve_assignable_department(
    db: AsyncSession, actor: CurrentUser, department_id: str | None
) -> str:
        """Department yang daftar calon assignee boleh dibaca aktor. superadmin tidak memiliki department, jadi wajib menyebutnya. peran lain hanya department sendiri"""
        if actor.role == "superadmin":
            if department_id is None:
                raise _unprocessable("departmentId is required for superadmin")
            if await DepartmentRepository.get_by_id(db, department_id) is None:
                raise _unprocessable("departmentId does not reference an existing department")
            return department_id
        if actor.department_id is None:
            raise _forbidden("User has no Department")
        if department_id is not None and department_id != actor.department_id:
            raise _forbidden("You can only list assignable users of your own Department")
        return actor.department_id



async def ensure_can_add(db: AsyncSession, actor: CurrentUser, request: Request) -> None:
    """Menambah assignment (keputusan A). Pemanggil sudah memastikan request terbaca (is_readable),
    jadi admin_department di sini pasti admin department penanggung jawab."""
    if actor.role in ("superadmin", "admin_department"):
        return
    if request.created_by_user_id == actor.id:
        return
    if await AssignmentRepository.has_active(db, request.id, actor.id):
        return
    raise _forbidden("Only the request creator, an active assignee, or admin_department can add assignments")



def ensure_can_release(actor: CurrentUser, assignment: RequestAssignment) -> None:
    """Melepas assignment (keputusan F): diri sendiri, atau admin_department di departemennya."""
    if actor.role in ("superadmin", "admin_department"):
        return
    if assignment.assignee_user_id == actor.id:
        return
    raise _forbidden("Only the assignee or admin_department can release this assignment")



def ensure_owns_assignment(actor: CurrentUser, assignment: RequestAssignment) -> None:
    """Jam kerja hanya dicatat, diubah, dan dihapus pemilik assignment (keputusan G)."""
    if assignment.assignee_user_id != actor.id:
        raise _forbidden("Only the assignee can record work hours on this assignment")



def resolve_create_assignments(
    actor: CurrentUser,
    design_type: DesignType,
    requested: list[tuple[str, WorkType]],
) -> list[tuple[str, WorkType]]:
    """Daftar assignment saat request dibuat (keputusan C).
    drafter / drafter_checker: selalu ikut. Bila tidak mencantumkan dirinya, di-assign ke
    semua work type di design_type. admin_department: wajib mengisi, tidak di-assign otomatis."""
    if len(set(requested)) != len(requested):
        raise _unprocessable("assignments contains a duplicate assigneeUserId and workType pair")
    if actor.role in SELF_ASSIGN_ROLES:
        if any(user_id == actor.id for user_id, _ in requested):
            return requested
        return [(actor.id, wt) for wt in WORK_TYPES_OF[design_type]] + requested
    if not requested:
        raise _unprocessable("assignments must contain at least one entry")
    return requested
