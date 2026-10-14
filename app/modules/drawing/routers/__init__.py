from fastapi import APIRouter

from app.modules.drawing.routers.cases import routerDrawingCase

router = APIRouter()
router.include_router(routerDrawingCase)