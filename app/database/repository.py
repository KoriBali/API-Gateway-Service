# app/repositories/staging_repository.py
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from app.database.models import StagingProject

class StagingRepository:
    @staticmethod
    async def save_staging_transaction(db: AsyncSession, project_entity: StagingProject):
        """
        Menyimpan parent (Project) beserta seluruh child-nya dalam satu transaksi.
        Jika satu gagal, seluruhnya akan rollback otomatis.
        """
        if project_entity.id:

            stmt = select(StagingProject).where(StagingProject.id == project_entity.id)
            result = await db.execute(stmt)
            existing_project = result.scalar_one_or_none()

            if existing_project:

                # Hapus project lama
                await db.delete(existing_project)

                # Create project baru dengan session_id yang sama
                await db.flush()

        db.add(project_entity)
        # Semua poles, conditions, dan direct_objects otomatis ikut tersimpan!
        
        await db.commit()
        await db.refresh(project_entity)
        
        return project_entity.id
    

    
    # Save to Main Database (soon)
    @staticmethod
    async def save_main_transaction(db:AsyncSession) -> str:
        """
        update Status di staging: pending -> save
        """



    # Get Staging Data
    @staticmethod
    async def get_staging_project_by_id(session_id: str, db: AsyncSession):
        """Mengambil data staging project beserta relasinya jika perlu"""
        stmt = select(StagingProject).where(StagingProject.id == session_id)
        # Jika butuh relasi sekalian, tambahkan .options(selectinload(...))
        
        result = await db.execute(stmt)
        return result.scalar_one_or_none()



    # Delete Staging Data
    @staticmethod
    async def delete_staging_project(session_id: str, db:AsyncSession) -> bool:

        # Ambil data project by session_id
        project = await StagingRepository.get_staging_project_by_id(session_id, db)

        if not project:
            return False
        
        await db.delete(project)
        await db.commit()

        return True
    

    # Delete by time
    @staticmethod
    async def delete_stale_projects(db: AsyncSession, days_threshold: int = 3) -> int:
        """
        Menghapus data staging project yang usianya lebih lama dari 'days_threshold'.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        print(datetime.now())
        
        stmt = delete(StagingProject).where(StagingProject.updated_at < cutoff_time)
        
        result = await db.execute(stmt)
        await db.commit()
        
        return result.rowcount