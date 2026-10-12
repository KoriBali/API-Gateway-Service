from fastapi import APIRouter

from app.modules.assignment.routers.assignments import routerAssignment

router = APIRouter()
router.include_router(routerAssignment)
