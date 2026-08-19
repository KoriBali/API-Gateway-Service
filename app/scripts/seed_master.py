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
    PoleCategory,
    PoleStandard,
    PoleStandardType,
    PoleDiameter,
    PoleCombination,
    PoleThickness,
    PoleThicknessPosition
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


# Pole Standard = Straight
STRAIGHT_COMBINATIONS = {
    "114.3": ["40-10", "40-12", "40-14", "40-20", "40-24", "40-30"],
    "139.8": ["50-10", "50-12", "50-14", "50-20", "50-24", "50-30", "50-34", "50-40"],
    "165.2": ["60-14", "60-20", "60-24", "60-30", "60-34", "60-40", "60-50"],
}
# ketebalan lower berdasarkan diameter lower (angka depan kombinasi)
STRAIGHT_THICKNESS = {"40": [3.5, 4.5, 6.0], "50": [3.5, 4.5, 6.6], "60": [3.7, 4.5, 5.0, 7.1]}




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


# Pole Standard = Straight
async def _seed_straight_pole(db):

    # Check category "lighting-pole" 
    res = await db.execute(
        select(PoleCategory).where(
            PoleCategory.name == "lighting-pole"
        )
    )

    category = res.scalar_one_or_none()

    if category is None:
        category = PoleCategory(name="lighting-pole")
        db.add(category)
        await db.flush()

    # Pastikan PoleStandard "Stepped Pole" untuk tipe straight
    res = await db.execute(
        select(PoleStandard).where(
            PoleStandard.pole_category_id == category.id,
            PoleStandard.type == PoleStandardType.straight,
        )
    )

    standard = res.scalar_one_or_none()

    if standard is None:
        standard = PoleStandard(
            pole_category_id=category.id,
            name="Stepped Pole",
            type=PoleStandardType.straight,
        )
        db.add(standard)
        await db.flush()

    # Seed diameter
    for diameter_str, combos in STRAIGHT_COMBINATIONS.items():
        diameter_value = float(diameter_str)

        res = await db.execute(
            select(PoleDiameter).where(
                PoleDiameter.pole_standard_id == standard.id,
                PoleDiameter.diameter == diameter_value,
            )
        )

        diameter = res.scalar_one_or_none()

        if diameter is None:
            diameter = PoleDiameter(
                pole_standard_id=standard.id,
                diameter=diameter_value,
            )
            db.add(diameter)
            await db.flush()

        # Seed combination
        for combo_name in combos:
            res = await db.execute(
                select(PoleCombination).where(
                    PoleCombination.pole_diameter_id == diameter.id,
                    PoleCombination.name == combo_name,
                )
            )

            combination = res.scalar_one_or_none()

            if combination is None:
                combination = PoleCombination(
                    pole_diameter_id=diameter.id,
                    name=combo_name,
                )
                db.add(combination)
                await db.flush()

            # Seed lower thickness
            lower_key = combo_name.split("-")[0]

            thicknesses = STRAIGHT_THICKNESS.get(lower_key, [])

            for thickness_value in thicknesses:
                res = await db.execute(
                    select(PoleThickness).where(
                        PoleThickness.pole_combination_id == combination.id,
                        PoleThickness.position == PoleThicknessPosition.lower,
                        PoleThickness.thickness == thickness_value,
                    )
                )

                thickness = res.scalar_one_or_none()

                if thickness is None:
                    db.add(
                        PoleThickness(
                            pole_combination_id=combination.id,
                            position=PoleThicknessPosition.lower,
                            thickness=thickness_value,
                        )
                    )


async def main():
    async with AsyncSessionLocal() as db:
        await _seed_simple_name(db, Material, MATERIALS)
        await _seed_simple_name(db, ObjectType, OBJECT_TYPES)
        await _seed_code_label(db, RegionCode, REGION_CODES)
        await _seed_code_label(db, DepartmentCode, DEPARTMENT_CODES)
        await _seed_code_label(db, AuthorCode, AUTHOR_CODES)
        await _seed_code_label(db, LightingCompanyCode, LIGHTING_COMPANY_CODES)
        await _seed_design_standards(db)
        await _seed_straight_pole(db)
        await db.commit()
    print("Seed master selesai.")


if __name__ == "__main__":
    asyncio.run(main())
