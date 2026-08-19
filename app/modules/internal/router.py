"""Route Remove Data Staging

Penghapusan Data Staging dilakukan dengan Cron Job
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.staging_database import get_db
from app.database.orchestrator import Orchestrator
from app.utils.response import success_response
from app.database.repository import StagingRepository



routerInternal = APIRouter(prefix="/api/internal", tags=["Internal System"])

INTERNAL_CLEANUP_TOKEN = settings.INTERNAL_CLEANUP_TOKEN

@routerInternal.delete("/cleanup-staging")
async def cleanup_staging_data(
    days: int = 3, 
    db: AsyncSession = Depends(get_db),
    x_internal_token: str = Header(..., description="secret token cron job"),
):
    if x_internal_token != INTERNAL_CLEANUP_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Forbidden: Invalid internal token"
        )
        
    # Memanggil Orchestrator yang ada di app/staging/orchestrator.py
    deleted_count = await Orchestrator.clean_expired_staging(
        db=db,
        days=days,
        clean_repo_func=StagingRepository.delete_stale_projects 
    )
    
    return success_response(
        data={"deleted_projects_count": deleted_count},
        message=f"Berhasil menghapus {deleted_count} abandoned project sessions."
    )