# app/repositories/staging_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.staging.models import StagingProject

class StagingRepository:
    @staticmethod
    async def save_staging_transaction(db: AsyncSession, project_entity: StagingProject) -> str:
        """
        Menyimpan parent (Project) beserta seluruh child-nya dalam satu transaksi.
        Jika satu gagal, seluruhnya akan rollback otomatis.
        """
        db.add(project_entity)
        # Semua poles, conditions, dan direct_objects otomatis ikut tersimpan!
        
        await db.commit()
        await db.refresh(project_entity)
        
        return project_entity.id