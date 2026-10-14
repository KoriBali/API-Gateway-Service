from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.workflow import NcChecklistItemMaster, WorkType

_MASTER_EDITABLE = ("step", "item", "sort_order", "is_active")



# ===== Daftar induk =====
class MasterItemRepository:

    @staticmethod
    async def list_items(
        db: AsyncSession, *, work_type: WorkType | None = None, include_inactive: bool = False,
    ) -> list[NcChecklistItemMaster]:
        stmt = select(NcChecklistItemMaster)
        if work_type is not None:
            stmt = stmt.where(NcChecklistItemMaster.work_type == work_type)
        if not include_inactive:
            stmt = stmt.where(NcChecklistItemMaster.is_active.is_(True))
        stmt = stmt.order_by(
            NcChecklistItemMaster.work_type,
            NcChecklistItemMaster.sort_order,
            NcChecklistItemMaster.created_at,
            NcChecklistItemMaster.id,
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get(db: AsyncSession, master_id: str) -> NcChecklistItemMaster | None:
        return await db.scalar(select(NcChecklistItemMaster).where(NcChecklistItemMaster.id == master_id))

    @staticmethod
    async def create(db: AsyncSession, data: dict) -> NcChecklistItemMaster:
        row = NcChecklistItemMaster(**data)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def update(db: AsyncSession, row: NcChecklistItemMaster, data: dict) -> NcChecklistItemMaster:
        for field in _MASTER_EDITABLE:
            if field in data:
                setattr(row, field, data[field])
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def work_types_without_active(db: AsyncSession, work_types) -> list[WorkType]:
        """Work type yang belum punya satu pun item master aktif. Checklist tanpa item untuk
        sebuah work type akan lolos gerbang tanpa pemeriksaan work type itu."""
        missing = []
        for work_type in work_types:
            found = await db.scalar(
                select(NcChecklistItemMaster.id).where(
                    NcChecklistItemMaster.work_type == work_type,
                    NcChecklistItemMaster.is_active.is_(True),
                ).limit(1)
            )
            if found is None:
                missing.append(work_type)
        return missing