from fastapi import APIRouter

from app.modules.project_tools.routers.calculation_pole import routerPoleTool

router = APIRouter()
router.include_router(routerPoleTool)
