from fastapi import APIRouter

from app.modules.assignment.routers.assignable_users import routerAssignableUser
from app.modules.assignment.routers.assignments import routerAssignment
from app.modules.assignment.routers.work_hours import routerWorkHour

router = APIRouter()
router.include_router(routerAssignment)
router.include_router(routerWorkHour)
router.include_router(routerAssignableUser)
