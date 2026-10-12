from fastapi import APIRouter

from app.modules.calculation.routers.calculate import routerCalculate
from app.modules.calculation.routers.cases import routerCalculationCase

router = APIRouter()
router.include_router(routerCalculate)
router.include_router(routerCalculationCase)