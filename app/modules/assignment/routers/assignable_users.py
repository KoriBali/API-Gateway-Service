from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.assignment import permissions
from app.modules.assignment.repository import AssignmentRepository
from app.modules.assignment.schemas import AssigneeRead

routerAssignableUser = APIRouter(prefix="/api/assignable-users", tags=["Request Assignment"])

_WORKER_ROLE =  require_roles("superadmin", "admin_department", "drafter_checker", "drafter")



# ===== Read =====
@routerAssignableUser.get("")
async def list_assignable_users(
    department_id: str | None = Query(default=None, alias="departmentId", min_length=1),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE)
):
    """untuk melihat data user disebuah department, berbeda dengan GET /api/users, endpoint ini data yang diberikan cukup ringkas"""
    department_id = await permissions.resolve_assignable_department(db, actor, department_id)
    
    rows = await AssignmentRepository.list_assignable_users(db, department_id, permissions.ASSIGNABLE_ROLES)
    return success_response(
        data = [AssigneeRead.model_validate(user) for user in rows],
        message = "Assignable users retrieved"
    )