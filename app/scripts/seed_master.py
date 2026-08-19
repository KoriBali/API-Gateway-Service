"""
File ini untuk inisiasi Data awal (seeding) table master

How to Run(pipenv shell):
    python -m app.scripts.seed_master
"""
import asyncio

from sqlalchemy import select

from app.core.staging_database import AsyncSessionLocal
from app.database.models import (
    Material,
    ObjectType,
    RegionCode,
    DepartmentCode,
    AuthorCode,
    LightingCompanyCode,
    DesignStandard,
    PoleCategory
)

MATERIALS = ["STK400", "STK490", "STK500", "STK590", "STKR400"]
OBJECT_TYPES = ["Omni", "Directional"]
REGION_CODES = [("A", "Area A"), ("B", "Area B"), ("C", "Area C"), ("D", "Area D"), ("E", "Area E")]
DEPARTMENT_CODES = [("V", "Author V"), ('W', "Author W"), ("Y", "Author Y"), ("Z", "Author Z")]
AUTHOR_CODES = [("R", "Department R"), ("I", "Department I"), ("F", "Department F"), ("S", "Koribali"), ("T", "Department T")]
LIGHTING_COMPANY_CODES = [("LEV-1761A22", "Koito"), ("E77257SAJ9", "Iwasaki"), ("NYR30031LF9", "Panasonic")]

DESIGN_STANDARDS = {
    "acemast": [
        {"name": "Standard Acts. (Law)"},
        {"name": "V60"},
        {"name": "Tower Standard"},
        {"name": "Haiden"},
    ],
    "lighting-pole": [
        {
            "name": "JIL",
            "defaultWindSpeed": 60,
            "defaultAirDensity": 1.23,
        },
        {"name": "Haiden"},
    ],
    "signboard": [
        {"name": "V60"},
        {"name": "Signboard"},
    ],
    "multiple" : [
        {"name" : "V60"},
        {"name" : "JIL"},
        {"name" : "Haiden"},
    ]
}



async def _seed_simple_name(db, model, names):
    # for table with only "name" column
    for name in names:
        exists = await db.execute(select(model).where(model.name == name))
        if exists.scalar_one_or_none() is None:
            db.add(model(name=name))


async def _seed_code_label(db, model, pairs):
    # for table with column 'code' and 'label'
    for code, label in pairs:
        exists = await db.execute(select(model).where(model.code == code))
        if exists.scalar_one_or_none() is None:
            db.add(model(code=code, label=label))


# Design Standard
async def _seed_design_standards(db):
    for category_name, standards in DESIGN_STANDARDS.items():
        # Search by Category
        res = await db.execute(select(PoleCategory).where(PoleCategory.name == category_name))

        category = res.scalar_one_or_none()

        if category is None:
            category = PoleCategory(name=category_name)
            db.add(category)
            await db.flush()

        for standard in standards:
            exists = await db.execute(
                select(DesignStandard).where(
                    DesignStandard.pole_category_id == category.id,
                    DesignStandard.name == standard["name"]
                )
            )

            if exists.scalar_one_or_none() is None:
                db.add(DesignStandard(
                    pole_category_id = category.id, 
                    name = standard["name"],
                    default_wind_speed = standard.get("defaultWindSpeed"),
                    default_air_density = standard.get("defaultAirDensity")
                    ))



async def main():
    async with AsyncSessionLocal() as db:
        await _seed_simple_name(db, Material, MATERIALS)
        await _seed_simple_name(db, ObjectType, OBJECT_TYPES)
        await _seed_code_label(db, RegionCode, REGION_CODES)
        await _seed_code_label(db, DepartmentCode, DEPARTMENT_CODES)
        await _seed_code_label(db, AuthorCode, AUTHOR_CODES)
        await _seed_code_label(db, LightingCompanyCode, LIGHTING_COMPANY_CODES)
        await _seed_design_standards(db)
        await db.commit()
    print("Seed master selesai.")


if __name__ == "__main__":
    asyncio.run(main())
