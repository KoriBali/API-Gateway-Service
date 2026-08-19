from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Material,
    ObjectType,
    RegionCode,
    DepartmentCode,
    AuthorCode,
    LightingCompanyCode,

    # Relational
    DesignStandard,
    PoleCategory
)


class MasterRepository:
    # Material
    @staticmethod
    async def list_materials(db: AsyncSession):
        # Select Material is_active = true
        stmt = select(Material).where(Material.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()


    # ObjectType
    @staticmethod
    async def list_object_types(db:AsyncSession):
        # Select Object type is_active = true
        stmt = select(ObjectType).where(ObjectType.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()


    # Region Code
    @staticmethod
    async def list_region_codes(db:AsyncSession):
        # Select Object type is_active = true
        stmt = select(RegionCode).where(RegionCode.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()


    # Department Code
    @staticmethod
    async def list_department_codes(db:AsyncSession):
        # Select Object type is_active = true
        stmt = select(DepartmentCode).where(DepartmentCode.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()


    # Author Code
    @staticmethod
    async def list_author_codes(db:AsyncSession):
        # Select Object type is_active = true
        stmt = select(AuthorCode).where(AuthorCode.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()


    # Lighting Company Code
    @staticmethod
    async def list_lighting_company_codes(db:AsyncSession):
        # Select Object type is_active = true
        stmt = select(LightingCompanyCode).where(LightingCompanyCode.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()



# =====================
# Relational Database
# =====================

    # Design Standards
    @staticmethod
    async def list_design_standards(db:AsyncSession, category:str | None = None):
        # Select Object type is_active = true
        stmt = select(DesignStandard).where(DesignStandard.is_active == True)

        if category:
            stmt = stmt.join(PoleCategory).where(PoleCategory.name == category)
        result = await db.execute(stmt)
        return result.scalars().all()
