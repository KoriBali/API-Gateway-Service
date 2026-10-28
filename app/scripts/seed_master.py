"""
File ini untuk inisiasi Data awal (seeding) Data Master

How to Run(pipenv shell):
    python -m app.scripts.seed_master
"""
import asyncio
from decimal import Decimal

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
    PoleStandardSegment,
    PoleStandardDirectObject,
    PoleType,
    ObjectKind,
    PoleHeightGroundPosition,
    PoleStandardType,
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
    Region,
    ExternalObject,
    ExternalObjectAvailability
)

MATERIALS = ["STK400", "STK490", "STK500", "STK590", "STKR400"]
OBJECT_TYPES = ["Omni", "Directional"]
REGION_CODES = [("A", "Area A"), ("B", "Area B"), ("C", "Area C"), ("D", "Area D"), ("E", "Area E")]
AUTHOR_CODES = [("V", "Author V"), ('W', "Author W"), ("Y", "Author Y"), ("Z", "Author Z")]
DEPARTMENT_CODES = [("R", "Department R"), ("I", "Department I"), ("F", "Department F"), ("S", "Koribali"), ("T", "Department T")]
LIGHTING_COMPANY_CODES = [("LEV-1761A22", "Koito"), ("E77257SAJ9", "Iwasaki"), ("NYR30031LF9", "Panasonic")]

DESIGN_STANDARDS = {
    "disaster_prevention": [
        {"name": "Standard Acts. (Law)"},
        {"name": "V60"},
        {"name": "Tower Standard"},
        {"name": "Haiden"},
    ],
    "lighting": [
        {
            "name": "Old JIL",
            "defaultWindSpeed": 60,
            "defaultAirDensity": 1.23,
        },
        {
            "name": "New JIL",
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
        {"name" : "Old JIL"},
        {"name" : "Haiden"},
    ]
}

# Nomor design standard yang dikirim ke engine, per nama (berlaku di semua kategori).
# Nama yang tidak ada di sini (Haiden, Signboard) tidak punya nomor dan tidak bisa dihitung.
DESIGN_STANDARD_CODES = {
    "Standard Acts. (Law)": 1,
    "V60": 2,
    "Old JIL": 3,
    "Tower Standard": 6,
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
    "on_gl": [8000, 10000, 12000],
    "under_gl": [8300, 10300, 12300],
}
TAPER_HEIGHTS_A = {
    "on_gl": [4500, 5000, 8000, 10000, 12000],
    "under_gl": [4800, 5300, 8300, 10300, 12300],
}

# ===== Geometri katalog taper =====
# Sumber: Spec_Taper_Pole_Standard.xlsx, sama dengan konstanta frontend. Baru IS yang
# diisi; tipe lain menyusul. Kunci = height on_gl (mm), nilai = (diameter bawah,
# diameter atas, tebal) dalam mm. Baris under_gl = height on_gl + 300 mm, dengan
# segmen straight 0.3 m yang tertanam di bawah garis tanah.
TAPER_GEOMETRY = {
    "IS": {
        8000: (165, 85, 4),
        10000: (175, 75, 4),
        12000: (195, 75, 4),
    },
}
TAPER_GEOMETRY_MATERIAL = "STK400"
UNDER_GL_OFFSET_MM = 300
UNDER_GL_EMBEDDED_M = Decimal("0.3")
TAPER_EVALUATED_POSITIONS_M = [Decimal("0")]
# Lampu IS
TAPER_LAMP = {
    "name": "灯具",
    "front_area_m2": Decimal("0.1"),
    "mass_per_unit_kg": Decimal("14"),
    "base_wind_coefficient": Decimal("1"),
    "quantity": 1,
}

def _offset_heights(heights, delta):
    return {gp: [h + delta for h in values] for gp, values in heights.items()}


# Type-L dan Type-T: height = seri dasar + 100 mm (on_gl maupun under_gl).
TAPER_HEIGHTS_S_PLUS_100 = _offset_heights(TAPER_HEIGHTS_S, 100)
TAPER_HEIGHTS_A_PLUS_100 = _offset_heights(TAPER_HEIGHTS_A, 100)

# code -> (label untuk ditampilkan, set height).
# CATATAN: TA sengaja memakai seri S (sesuai HEIGHT_OPTIONS_BY_STANDARD di frontend).
TAPER_POLES = {
    "IS": {"label": "Type-I (IS)", "heights": TAPER_HEIGHTS_S},
    "IA": {"label": "Type-I (IA)", "heights": TAPER_HEIGHTS_A},
    "LS": {"label": "Type-L (LS)", "heights": TAPER_HEIGHTS_S_PLUS_100},
    "LA": {"label": "Type-L (LA)", "heights": TAPER_HEIGHTS_A_PLUS_100},
    "TS": {"label": "Type-T (TS)", "heights": TAPER_HEIGHTS_S_PLUS_100},
    "TA": {"label": "Type-T (TA)", "heights": TAPER_HEIGHTS_S_PLUS_100},
}



# ===== Coupling =====
COUPLING_POSITIONS = [("front", "Front"), ("right", "Right"), ("back", "Back"), ("left", "Left")]
COUPLING_SIZES = [("#16","#16"),("#22","#22"),("#28","#28"),("#36","#36"),("#42","#42"),("#54","#54"),("#70","#70")]
COUPLING_TYPES = [("jis","JIS"),("standard","Standard"),("short","Short"),("long","Long")]



# ===== Region (zona utility) =====
REGIONS = [
    # (code, label)
    ("east_japan", "East Japan"),
    ("west_japan", "West Japan"),
]

# ===== External Object =====
EXTERNAL_OBJECTS = [
    # (code, label)
    ("yupilon_bushing", "Yupilon Bushing"),
    ("nipple", "Nipple"),
    ("terminal_cap", "Terminal Cap"),
]

# ===== Matriks availability External Object =====
# (region_code, external_object_code, avail_when_zero, avail_when_nonzero)
# West: keputusan stakeholder (adopsi matriks FE) — menimpa KB lama. Lihat memory
# coupling-west-availability-conflict. West = bushing@≠0, terminal_cap@0, nipple tak pernah.
EXTERNAL_OBJECT_AVAILABILITY = [
    ("east_japan", "yupilon_bushing", False, True),
    ("east_japan", "nipple",          True,  True),
    ("east_japan", "terminal_cap",    True,  False),
    ("west_japan", "yupilon_bushing", False, True),
    ("west_japan", "terminal_cap",    True,  False),
    # west_japan/nipple sengaja tak ada (tak pernah available)
]


# Couple case number
S, PD, PA = CouplingShape.single, CouplingShape.pair_distance, CouplingShape.pair_angular
COUPLING_CASES = [
    (1,  1, S,  None, None, None),
    (2,  1, PD, None, "d",  None),
    (3,  1, PA, None, "θ",  None),
    (4,  2, S,  S,    None, None),
    (5,  1, PA, None, "θ1", None),
    (6,  2, PD, PD,   "d",  "d"),
    (7,  2, PA, PA,   "01",  "02"),
    (8,  2, S,  PD,   None, "d"),
    (9,  2, S,  PA,   None, "02"),
    (10, 2, S,  PA,   None, "θ2"),
]



# ===== Pole Diagram ==== 
POLE_DIAGRAMS = {
    "IS": {
        "baseplate": {"on_gl": "/images/IS-Type-OnGL.svg", "under_gl": "/images/IS-Type-UnderGL.svg"},
        "embed": {None: "/images/IS-Type-Embed.svg"},
    },
    "IA": {
        "baseplate": {"on_gl": "/images/IA-Type-OnGL.svg", "under_gl": "/images/IA-Type-UnderGL.svg"},
        "embed": {None: "/images/IA-Type-Embed.svg"},
    },
    "LS": {
        "baseplate": {"on_gl": "/images/LS-Type-OnGL.svg", "under_gl": "/images/LS-Type-UnderGL.svg"},
        "embed": {None: "/images/LS-Type-Embed.svg"},
    },
    "LA": {
        "baseplate": {"on_gl": "/images/LA-Type-OnGL.svg", "under_gl": "/images/LA-Type-UnderGL.svg"},
        "embed": {None: "/images/LA-Type-Embed.svg"},
    },
    "TS": {
        "baseplate": {"on_gl": "/images/TS-Type-OnGL.svg", "under_gl": "/images/TS-Type-UnderGL.svg"},
        "embed": {None: "/images/TS-Type-Embed.svg"},
    },
    "TA": {
        "baseplate": {"on_gl": "/images/TA-Type-OnGL.svg", "under_gl": "/images/TA-Type-UnderGL.svg"},
        "embed": {None: "/images/TA-Type-Embed.svg"},
    },
}



async def _seed_regions(db):
    for index, (code, label) in enumerate(REGIONS):
        exists = await db.execute(select(Region).where(Region.code == code))
        if exists.scalar_one_or_none() is None:
            db.add(Region(code=code, label=label, sort_order=index))


async def _seed_external_objects(db):
    for index, (code, label) in enumerate(EXTERNAL_OBJECTS):
        exists = await db.execute(select(ExternalObject).where(ExternalObject.code == code))
        if exists.scalar_one_or_none() is None:
            db.add(ExternalObject(code=code, label=label, sort_order=index))


async def _seed_external_object_availability(db):
    # region & external_object harus sudah ada → flush dulu di main() sebelum fungsi ini
    for region_code, eo_code, when_zero, when_nonzero in EXTERNAL_OBJECT_AVAILABILITY:
        region = (await db.execute(select(Region).where(Region.code == region_code))).scalar_one_or_none()
        eo = (await db.execute(select(ExternalObject).where(ExternalObject.code == eo_code))).scalar_one_or_none()
        if region is None or eo is None:
            continue  
        exists = await db.execute(
            select(ExternalObjectAvailability).where(
                ExternalObjectAvailability.region_id == region.id,
                ExternalObjectAvailability.external_object_id == eo.id,
            )
        )
        if exists.scalar_one_or_none() is None:
            db.add(ExternalObjectAvailability(
                region_id=region.id,
                external_object_id=eo.id,
                avail_when_zero=when_zero,
                avail_when_nonzero=when_nonzero,
            ))



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
    for num, groups, cp1, cp2, cp1_label, cp2_label in COUPLING_CASES:
        exists = await db.execute(select(CouplingCase).where(CouplingCase.case_number == num))
        if exists.scalar_one_or_none() is None:
            db.add(CouplingCase(
                case_number=num,
                num_groups=groups,
                cp1_shape=cp1,
                cp2_shape=cp2,
                cp1_label=cp1_label,
                cp2_label=cp2_label,
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

            code = DESIGN_STANDARD_CODES.get(standard["name"])
            row = exists.scalar_one_or_none()
            if row is None:
                db.add(DesignStandard(
                    pole_category_id = category.id, 
                    name = standard["name"],
                    code = code,
                    default_wind_speed = standard.get("defaultWindSpeed"),
                    default_air_density = standard.get("defaultAirDensity")
                    ))
            elif row.code is None and code is not None:
                # DB yang di-migrate tanpa reset: isi nomor yang masih kosong, tidak menimpa.
                row.code = code



# Pole Standard = Straight
async def _seed_straight_pole(db):

    # Check category "lighting" 
    res = await db.execute(
        select(PoleCategory).where(
            PoleCategory.name == "lighting"
        )
    )

    category = res.scalar_one_or_none()

    if category is None:
        category = PoleCategory(name="lighting")
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

    # Pastikan category "lighting" ada (dipakai bersama straight)
    res = await db.execute(
        select(PoleCategory).where(PoleCategory.name == "lighting")
    )
    category = res.scalar_one_or_none()

    if category is None:
        category = PoleCategory(name="lighting")
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



# Geometri taper per pilihan tinggi
async def _seed_taper_geometry(db):
    material = (await db.execute(
        select(Material).where(Material.name == TAPER_GEOMETRY_MATERIAL)
    )).scalar_one()

    for code, rows in TAPER_GEOMETRY.items():
        standard = (await db.execute(
            select(PoleStandard).where(
                PoleStandard.type == PoleStandardType.taper,
                PoleStandard.code == code,
            )
        )).scalar_one()

        for on_gl_mm, (diameter_lower, diameter_upper, thickness) in rows.items():
            for ground_position in (PoleHeightGroundPosition.on_gl, PoleHeightGroundPosition.under_gl):
                is_under_gl = ground_position == PoleHeightGroundPosition.under_gl
                height_mm = on_gl_mm + (UNDER_GL_OFFSET_MM if is_under_gl else 0)

                # Baris height dibuat _seed_taper_pole; tidak ada berarti konstanta tidak sinkron.
                height = (await db.execute(
                    select(PoleStandardHeight).where(
                        PoleStandardHeight.pole_standard_id == standard.id,
                        PoleStandardHeight.ground_position == ground_position,
                        PoleStandardHeight.height == height_mm,
                    )
                )).scalar_one()

                # Isi bila kosong, tidak menimpa.
                if height.gl_elevation_m is None:
                    height.gl_elevation_m = UNDER_GL_EMBEDDED_M if is_under_gl else Decimal("0")
                if height.evaluated_positions_m is None:
                    height.evaluated_positions_m = list(TAPER_EVALUATED_POSITIONS_M)

                # Idempotent per pilihan tinggi: segmen dan lampu hanya dibuat bila belum ada sama sekali.
                has_segments = (await db.execute(
                    select(PoleStandardSegment.id).where(
                        PoleStandardSegment.pole_standard_height_id == height.id
                    ).limit(1)
                )).scalar_one_or_none()
                if has_segments is None:
                    db.add(PoleStandardSegment(
                        pole_standard_height_id=height.id,
                        material_id=material.id,
                        name="Pole-1",
                        pole_type=PoleType.taper,
                        top_elevation_m=Decimal(height_mm) / 1000,
                        diameter_lower_mm=diameter_lower,
                        diameter_upper_mm=diameter_upper,
                        thickness_lower_mm=thickness,
                        thickness_upper_mm=thickness,
                    ))
                    if is_under_gl:
                        db.add(PoleStandardSegment(
                            pole_standard_height_id=height.id,
                            material_id=material.id,
                            name="Pole-2",
                            pole_type=PoleType.straight,
                            top_elevation_m=UNDER_GL_EMBEDDED_M,
                            diameter_lower_mm=diameter_lower,
                            thickness_lower_mm=thickness,
                        ))

                has_objects = (await db.execute(
                    select(PoleStandardDirectObject.id).where(
                        PoleStandardDirectObject.pole_standard_height_id == height.id
                    ).limit(1)
                )).scalar_one_or_none()
                if has_objects is None:
                    db.add(PoleStandardDirectObject(
                        pole_standard_height_id=height.id,
                        object_kind=ObjectKind.omni,
                        elevation_m=Decimal(on_gl_mm) / 1000,
                        **TAPER_LAMP,
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
        await _seed_straight_pole(db)
        await _seed_taper_pole(db)
        await _seed_taper_pole(db)
        await _seed_taper_geometry(db)
        await _seed_code_label_ordered(db, CouplingPosition, COUPLING_POSITIONS)
        await _seed_code_label_ordered(db, CouplingSize, COUPLING_SIZES)
        await _seed_code_label_ordered(db, CouplingType, COUPLING_TYPES)
        await _seed_coupling_cases(db)
        await _seed_pole_diagrams(db)   
        await _seed_regions(db)
        await _seed_external_objects(db)
        await db.flush()
        await _seed_external_object_availability(db)
        await db.commit()
    print("Seed master selesai.")


if __name__ == "__main__":
    asyncio.run(main())
