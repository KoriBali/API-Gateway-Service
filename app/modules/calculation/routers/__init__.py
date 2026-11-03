from fastapi import APIRouter

from app.modules.calculation.routers.cases import routerCalculationCase
from app.modules.calculation.routers.runs import routerCalculationRun
from app.modules.calculation.routers.report_header import routerReportHeader
from app.modules.calculation.routers.draft import routerCalculationDraft

router = APIRouter()
router.include_router(routerCalculationCase)
router.include_router(routerCalculationRun)
router.include_router(routerReportHeader)
router.include_router(routerCalculationDraft)
