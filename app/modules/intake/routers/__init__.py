from fastapi import APIRouter

from app.modules.intake.routers.projects import routerProject
from app.modules.intake.routers.requests import routerRequest

router = APIRouter()
router.include_router(routerProject)
router.include_router(routerRequest)