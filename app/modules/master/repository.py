from sqlalchemy import select
from sqlalchemy.orm import selectinload
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
    PoleCategory,

    # Pole standard
    PoleStandard,
    PoleStandardType,
    PoleDiameter,
    PoleCombination
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
        # Region Code type is_active = true
        stmt = select(RegionCode).where(RegionCode.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()


    # Department Code
    @staticmethod
    async def list_department_codes(db:AsyncSession):
        # Department Code type is_active = true
        stmt = select(DepartmentCode).where(DepartmentCode.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()


    # Author Code
    @staticmethod
    async def list_author_codes(db:AsyncSession):
        # Author Code type is_active = true
        stmt = select(AuthorCode).where(AuthorCode.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()


    # Lighting Company Code
    @staticmethod
    async def list_lighting_company_codes(db:AsyncSession):
        # Lighting Company Code type is_active = true
        stmt = select(LightingCompanyCode).where(LightingCompanyCode.is_active == True)
        result = await db.execute(stmt)
        return result.scalars().all()



# =====================
# Relational Database
# =====================

    # Design Standards
    @staticmethod
    async def list_design_standards(db:AsyncSession, category:str | None = None):
        # Design Standards type is_active = true
        stmt = select(DesignStandard).where(DesignStandard.is_active == True)

        if category:
            stmt = stmt.join(PoleCategory).where(PoleCategory.name == category)
        result = await db.execute(stmt)
        return result.scalars().all()


    # Pole Standards 
    @staticmethod
    async def list_pole_standards(db:AsyncSession, category: str | None = None, type: str | None = None):
        stmt = (
            select(PoleStandard)
            .where(PoleStandard.is_active == True)
            .options(
                selectinload(PoleStandard.pole_standard_heights),
                selectinload(PoleStandard.pole_diameters)
                .selectinload(PoleDiameter.pole_combinations)
                .selectinload(PoleCombination.pole_thicknesses)
            )
        )

        if category:
            stmt = stmt.join(PoleCategory).where(PoleCategory.name == category)

        if type:
            stmt = stmt.where(PoleStandard.type == PoleStandardType(type))

        result = await db.execute(stmt)
        return result.scalars().all()