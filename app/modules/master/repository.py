from sqlalchemy import select, or_
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
    PoleCombination,

    # Coupling
    Region,
    ExternalObjectAvailability,
    ExternalObject,
    CouplingCase,
    CouplingPosition,
    CouplingSize,
    CouplingType
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



    @staticmethod
    async def list_regions(db: AsyncSession):
        stmt = select(Region).where(Region.is_active == True).order_by(Region.sort_order)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def list_external_objects(db: AsyncSession):
        stmt = select(ExternalObject).where(ExternalObject.is_active == True).order_by(ExternalObject.sort_order)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def list_eo_availabilities(db: AsyncSession):
        stmt = select(ExternalObjectAvailability)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def list_coupling_positions(db: AsyncSession):
        stmt = select(CouplingPosition).where(CouplingPosition.is_active == True).order_by(CouplingPosition.sort_order)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def list_coupling_sizes(db: AsyncSession):
        stmt = select(CouplingSize).where(CouplingSize.is_active == True).order_by(CouplingSize.sort_order)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def list_coupling_types(db: AsyncSession):
        stmt = select(CouplingType).where(CouplingType.is_active == True).order_by(CouplingType.sort_order)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def list_coupling_cases(db: AsyncSession):
        stmt = select(CouplingCase).where(CouplingCase.is_active == True).order_by(CouplingCase.sort_order)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def get_region(db: AsyncSession, ref: str):
        # Terima code (mis. "east_japan") ATAU id (UUID) — hilangkan silent-empty.
        stmt = select(Region).where(or_(Region.code == ref, Region.id == ref))
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def resolve_external_objects(db: AsyncSession, region_id: str, is_zero: bool):
        col = ExternalObjectAvailability.avail_when_zero if is_zero else ExternalObjectAvailability.avail_when_nonzero
        stmt = (
            select(ExternalObject)
            .join(ExternalObjectAvailability, ExternalObjectAvailability.external_object_id == ExternalObject.id)
            .where(ExternalObjectAvailability.region_id == region_id, col == True, ExternalObject.is_active == True)
            .order_by(ExternalObject.sort_order)
        )
        return (await db.execute(stmt)).scalars().all()


