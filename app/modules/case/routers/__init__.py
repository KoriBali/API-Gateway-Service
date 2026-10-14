from fastapi import APIRouter

from app.modules.case.routers.cases import routerCase
from app.modules.case.routers.check_queue import routerCheckQueue

router = APIRouter()
router.include_router(routerCase)
router.include_router(routerCheckQueue)