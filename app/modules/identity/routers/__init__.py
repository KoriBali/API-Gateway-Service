from fastapi import APIRouter

from app.modules.identity.routers.auth import routerAuth
from app.modules.identity.routers.users import routerUsers
from app.modules.identity.routers.departments import routerDepartment
from app.modules.identity.routers.requests import routerRequest

router = APIRouter()
router.include_router(routerAuth)
router.include_router(routerUsers)
router.include_router(routerDepartment)
router.include_router(routerRequest)