from fastapi import APIRouter

from app.modules.checklist.routers.masters import routerChecklistMaster

router = APIRouter()
router.include_router(routerChecklistMaster)