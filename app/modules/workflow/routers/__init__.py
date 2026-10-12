from fastapi import APIRouter

from app.modules.workflow.routers.events import routerRequestEvent

router = APIRouter()
router.include_router(routerRequestEvent)