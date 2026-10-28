from fastapi import APIRouter

from app.modules.calculation.routers.cases import routerCalculationCase
from app.modules.calculation.routers.runs import routerCalculationRun

router = APIRouter()
router.include_router(routerCalculationCase)
router.include_router(routerCalculationRun)