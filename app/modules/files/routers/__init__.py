from fastapi import APIRouter

from app.modules.files.routers.attachments import routerAttachment
from app.modules.files.routers.files import routerFile
from app.modules.files.routers.local_storage import routerLocalStorage

router = APIRouter()
router.include_router(routerFile)
router.include_router(routerAttachment)
router.include_router(routerLocalStorage)
