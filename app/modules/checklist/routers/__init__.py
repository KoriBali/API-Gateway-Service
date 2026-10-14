from fastapi import APIRouter

from app.modules.checklist.routers.masters import routerChecklistMaster
from app.modules.checklist.routers.checklists import routerChecklist

router = APIRouter()
router.include_router(routerChecklistMaster)
router.include_router(routerChecklist)
