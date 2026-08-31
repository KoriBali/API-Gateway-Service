"""
File ini untuk inisiasi Data awal (seeding) Data Master

How to Run(pipenv shell):
    python -m app.scripts.seed_master
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
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
    PoleStandardHeight,
    PoleHeightGroundPosition,
    PoleStandardType,
    PoleDiameter,
    PoleCombination,
    PoleThickness,
    PoleThicknessPosition,
    CouplingCase, 
    CouplingShape,
    CouplingPosition, 
    CouplingSize, 
    CouplingType,
    PoleDiagram, 
    PoleMounting, 
)

MATERIALS = ["STK400", "STK490", "STK500", "STK590", "STKR400"]
OBJECT_TYPES = ["Omni", "Directional"]
REGION_CODES = [("A", "Area A"), ("B", "Area B"), ("C", "Area C"), ("D", "Area D"), ("E", "Area E")]
AUTHOR_CODES = [("V", "Author V"), ('W', "Author W"), ("Y", "Author Y"), ("Z", "Author Z")]
DEPARTMENT_CODES = [("R", "Department R"), ("I", "Department I"), ("F", "Department F"), ("S", "Koribali"), ("T", "Department T")]
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


# ===== Pole Standard = Straight =====
STRAIGHT_COMBINATIONS = {
    "114.3": ["40-10", "40-12", "40-14", "40-20", "40-24", "40-30"],
    "139.8": ["50-10", "50-12", "50-14", "50-20", "50-24", "50-30", "50-34", "50-40"],
    "165.2": ["60-14", "60-20", "60-24", "60-30", "60-34", "60-40", "60-50"],
}
# ketebalan lower berdasarkan diameter lower (angka depan kombinasi)
STRAIGHT_THICKNESS = {"40": [3.5, 4.5, 6.0], "50": [3.5, 4.5, 6.6], "60": [3.7, 4.5, 5.0, 7.1]}


# ===== Pole Standard = Taper =====
# Height dibedakan per ground position (mengikuti konstanta frontend).
TAPER_HEIGHTS_S = {
    "on_GL": [8.0, 10.0, 12.0],
    "under_GL": [8.3, 10.3, 12.3],
}
TAPER_HEIGHTS_A = {
    "on_GL": [4.5, 5.0, 8.0, 10.0, 12.0],
    "under_GL": [4.8, 5.3, 8.3, 10.3, 12.3],
}

# code -> (label untuk ditampilkan, set height).
# CATATAN: TA sengaja memakai seri S (sesuai HEIGHT_OPTIONS_BY_STANDARD di frontend).
TAPER_POLES = {
    "IS": {"label": "Type-I (IS)", "heights": TAPER_HEIGHTS_S},
    "IA": {"label": "Type-I (IA)", "heights": TAPER_HEIGHTS_A},
    "LS": {"label": "Type-L (LS)", "heights": TAPER_HEIGHTS_S},
    "LA": {"label": "Type-L (LA)", "heights": TAPER_HEIGHTS_A},
    "TS": {"label": "Type-T (TS)", "heights": TAPER_HEIGHTS_S},
    "TA": {"label": "Type-T (TA)", "heights": TAPER_HEIGHTS_S},
}



# ===== Coupling =====
COUPLING_POSITIONS = [("front", "Front"), ("right", "Right"), ("back", "Back"), ("left", "Left")]
COUPLING_SIZES = [("#16","#16"),("#22","#22"),("#28","#28"),("#36","#36"),("#42","#42"),("#54","#54"),("#70","#70")]
COUPLING_TYPES = [("JIS","JIS"),("standard","Standard"),("short","Short"),("long","Long")]



# Couple case number
S, PD, PA = CouplingShape.single, CouplingShape.pair_distance, CouplingShape.pair_angular
COUPLING_CASES = [
    (1, 1, S,  None, True),
    (2, 1, PD, None, False),
    (3, 1, PA, None, False),
    (4, 2, S,  S,    False),
    (5, 1, PA, None, False),  
    (6, 2, PD, PD,   False),
    (7, 2, PA, PA,   False),
    (8, 2, S,  PD,   False),
    (9, 2, S,  PA,   False),
    (10,2, S,  PA,   False),  
]



# ===== Pole Diagram ==== 
POLE_DIAGRAMS = {
    "IS": {
        "baseplate": {"on_GL": "/images/IS-Type-OnGL.svg", "under_GL": "/images/IS-Type-UnderGL.svg"},
        "embed": {None: "/images/IS-Type-Embed.svg"},
    },
    "IA": {
        "baseplate": {"on_GL": "/images/IA-Type-OnGL.svg", "under_GL": "/images/IA-Type-UnderGL.svg"},
        "embed": {None: "/images/IA-Type-Embed.svg"},
    },
    "LS": {
        "baseplate": {"on_GL": "/images/LS-Type-OnGL.svg", "under_GL": "/images/LS-Type-UnderGL.svg"},
        "embed": {None: "/images/LS-Type-Embed.svg"},
    },
    "LA": {
        "baseplate": {"on_GL": "/images/LA-Type-OnGL.svg", "under_GL": "/images/LA-Type-UnderGL.svg"},
        "embed": {None: "/images/LA-Type-Embed.svg"},
    },
    "TS": {
        "baseplate": {"on_GL": "/images/TS-Type-OnGL.svg", "under_GL": "/images/TS-Type-UnderGL.svg"},
        "embed": {None: "/images/TS-Type-Embed.svg"},
    },
    "TA": {
        "baseplate": {"on_GL": "/images/TA-Type-OnGL.svg", "under_GL": "/images/TA-Type-UnderGL.svg"},
        "embed": {None: "/images/TA-Type-Embed.svg"},
    },
}



async def _seed_pole_diagrams(db):
    for code, mountings in POLE_DIAGRAMS.items():
        res = await db.execute(select(PoleStandard).where(PoleStandard.code == code))
        std = res.scalar_one_or_none()
        if std is None:
            continue  # taper harus sudah di-seed oleh _seed_taper_pole
        for mounting_str, grounds in mountings.items():
            for ground_str, url in grounds.items():
                gp = PoleHeightGroundPosition(ground_str) if ground_str else None
                exists = await db.execute(select(PoleDiagram).where(
                    PoleDiagram.pole_standard_id == std.id,
                    PoleDiagram.mounting == PoleMounting(mounting_str),
                    PoleDiagram.ground_position == gp,
                ))
                if exists.scalar_one_or_none() is None:
                    db.add(PoleDiagram(pole_standard_id=std.id,
                                       mounting=PoleMounting(mounting_str),
                                       ground_position=gp, image_url=url))



async def _seed_coupling_cases(db):
    for num, groups, cp1, cp2, eo in COUPLING_CASES:
        exists = await db.execute(select(CouplingCase).where(CouplingCase.case_number == num))
        if exists.scalar_one_or_none() is None:
            db.add(CouplingCase(
                case_number=num,
                num_groups=groups,
                cp1_shape=cp1,
                cp2_shape=cp2,
                external_object_required=eo,
                image_url=f"/images/CP-Case{num}.svg",
                detail_image_url=f"/images/CPdetail-Case{num}.svg",
                sort_order=num,
            ))



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



async def _seed_code_label_ordered(db, model, pairs):
    # sama seperti _seed_code_label, tapi isi sort_order = posisi di list (0,1,2,...)
    for index, (code, label) in enumerate(pairs):
        exists = await db.execute(select(model).where(model.code == code))
        if exists.scalar_one_or_none() is None:
            db.add(model(code=code, label=label, sort_order=index))



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
            code="steppedPole",
            name="Stepped Pole",
            type=PoleStandardType.straight,
        )
        db.add(standard)
        await db.flush()
    elif standard.code is None:
        # Backfill code untuk baris yang di-seed sebelum kolom `code` ada
        standard.code = "steppedPole"

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



# Pole Standard = Taper
async def _seed_taper_pole(db):

    # Pastikan category "lighting-pole" ada (dipakai bersama straight)
    res = await db.execute(
        select(PoleCategory).where(PoleCategory.name == "lighting-pole")
    )
    category = res.scalar_one_or_none()

    if category is None:
        category = PoleCategory(name="lighting-pole")
        db.add(category)
        await db.flush()

    for code, config in TAPER_POLES.items():
        # PENTING: filter menyertakan `code`, karena taper punya BANYAK
        # PoleStandard bertipe taper (beda dengan straight yang cuma satu).
        res = await db.execute(
            select(PoleStandard).where(
                PoleStandard.pole_category_id == category.id,
                PoleStandard.type == PoleStandardType.taper,
                PoleStandard.code == code,
            )
        )
        standard = res.scalar_one_or_none()

        if standard is None:
            standard = PoleStandard(
                pole_category_id=category.id,
                code=code,
                name=config["label"],
                type=PoleStandardType.taper,
            )
            db.add(standard)
            await db.flush()

        # Seed height per ground position (idempotent per baris)
        for gp_value, heights in config["heights"].items():
            ground_position = PoleHeightGroundPosition(gp_value)

            for height_value in heights:
                res = await db.execute(
                    select(PoleStandardHeight).where(
                        PoleStandardHeight.pole_standard_id == standard.id,
                        PoleStandardHeight.ground_position == ground_position,
                        PoleStandardHeight.height == height_value,
                    )
                )

                if res.scalar_one_or_none() is None:
                    db.add(
                        PoleStandardHeight(
                            pole_standard_id=standard.id,
                            ground_position=ground_position,
                            height=height_value,
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
        await _seed_taper_pole(db)
        await _seed_code_label_ordered(db, CouplingPosition, COUPLING_POSITIONS)
        await _seed_code_label_ordered(db, CouplingSize, COUPLING_SIZES)
        await _seed_code_label_ordered(db, CouplingType, COUPLING_TYPES)
        await _seed_coupling_cases(db)
        await _seed_pole_diagrams(db)   
        await db.commit()
    print("Seed master selesai.")


if __name__ == "__main__":
    asyncio.run(main())
