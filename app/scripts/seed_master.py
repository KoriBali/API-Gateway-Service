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
    PoleStandardStepPole,
    PoleStandardDirectObject,
    PoleStandardArm,
    PoleStandardArmObject,
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
        {"name": "Act Disaster Prevention"},
        {"name": "Fixed Wind Disaster Prevention"},
        {"name": "Act Tower"},
        {"name": "Haiden Kitei"},
    ],
    "lighting": [
        {
            "name": "Old Lighting Pole",
            "defaultWindSpeed": 60,
            "defaultAirDensity": 1.23,
        },
        {
            "name": "New JIL",
            "defaultWindSpeed": 60,
            "defaultAirDensity": 1.23,
            "defaultHorizontalAcceleration": 4.71,
            "defaultResponseRatio": 1.0,
        },
        {"name": "Haiden Kitei"},
    ],
    "signboard": [
        {"name": "Fixed Wind Disaster Prevention"},
        {"name": "Signboard"},
    ],
    "multiple" : [
        {"name" : "Fixed Wind Disaster Prevention"},
        {"name" : "Old Lighting Pole"},
        {"name" : "Haiden Kitei"},
    ]
}

# Nomor design standard yang dikirim ke engine, per nama (berlaku di semua kategori).
# Nama dan nomor mengikuti DesignStandardCode Calculation Service. Nama yang tidak ada di
# sini (Signboard) tidak punya nomor. Yang bisa dihitung ditentukan CALCULABLE_DESIGN_STANDARDS.
DESIGN_STANDARD_CODES = {
    "Act Disaster Prevention": 1,
    "Fixed Wind Disaster Prevention": 2,
    "Old Lighting Pole": 3,
    "Act Tower": 6,
    "New JIL": 7,
    "Haiden Kitei": 8,
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
# Disusun mekanis dari 44 payload uji taper (JSON) yang hasilnya sudah dicocokkan
# dengan perhitungan referensi.
# Kunci = (ground position, height label dalam mm). Tiap step pole dari yang teratas:
# (bentuk, top elevation mm, diameter bawah mm, diameter atas mm; None untuk straight).
# evaluated_mm = posisi cek, urut seperti payload (tipe A: puncak taper lalu dasar tiang).
# lamp_mm = elevasi lampu pada objek langsung (tipe I).
# arm_mm + arm_angles = elevasi pasang dan sudut tiap lengan (tipe L satu, tipe T dua).
TAPER_GEOMETRY = {
    "IS": {
        ("on_gl", 8000): {"step_poles": [("taper", 8000, 165, 85)], "evaluated_mm": [0], "lamp_mm": 8000},
        ("under_gl", 8300): {"step_poles": [("taper", 8300, 165, 85), ("straight", 300, 165, None)], "evaluated_mm": [0], "lamp_mm": 8300},
        ("on_gl", 10000): {"step_poles": [("taper", 10000, 175, 75)], "evaluated_mm": [0], "lamp_mm": 10000},
        ("under_gl", 10300): {"step_poles": [("taper", 10300, 175, 75), ("straight", 300, 175, None)], "evaluated_mm": [0], "lamp_mm": 10300},
        ("on_gl", 12000): {"step_poles": [("taper", 12000, 195, 75)], "evaluated_mm": [0], "lamp_mm": 12000},
        ("under_gl", 12300): {"step_poles": [("taper", 12300, 195, 75), ("straight", 300, 195, None)], "evaluated_mm": [0], "lamp_mm": 12300},
    },
    "IA": {
        ("on_gl", 4500): {"step_poles": [("straight", 4500, 75, None), ("taper", 3405, 165, 75), ("straight", 1500, 165, None)], "evaluated_mm": [3405, 0], "lamp_mm": 4500},
        ("under_gl", 4800): {"step_poles": [("straight", 4800, 75, None), ("taper", 3705, 165, 75), ("straight", 1800, 165, None)], "evaluated_mm": [3705, 0], "lamp_mm": 4800},
        ("on_gl", 5000): {"step_poles": [("straight", 5000, 75, None), ("taper", 3405, 165, 75), ("straight", 1500, 165, None)], "evaluated_mm": [3405, 0], "lamp_mm": 5000},
        ("under_gl", 5300): {"step_poles": [("straight", 5300, 75, None), ("taper", 3705, 165, 75), ("straight", 1800, 165, None)], "evaluated_mm": [3705, 0], "lamp_mm": 5300},
        ("on_gl", 8000): {"step_poles": [("straight", 8000, 75, None), ("taper", 6500, 165, 75), ("straight", 1500, 165, None)], "evaluated_mm": [6500, 0], "lamp_mm": 8000},
        ("under_gl", 8300): {"step_poles": [("straight", 8300, 75, None), ("taper", 6800, 165, 75), ("straight", 1800, 165, None)], "evaluated_mm": [6800, 0], "lamp_mm": 8300},
        ("on_gl", 10000): {"step_poles": [("straight", 10000, 75, None), ("taper", 7500, 175, 75), ("straight", 1500, 175, None)], "evaluated_mm": [7500, 0], "lamp_mm": 10000},
        ("under_gl", 10300): {"step_poles": [("straight", 10300, 75, None), ("taper", 7800, 175, 75), ("straight", 1800, 175, None)], "evaluated_mm": [7800, 0], "lamp_mm": 10300},
        ("on_gl", 12000): {"step_poles": [("straight", 12000, 75, None), ("taper", 9500, 195, 75), ("straight", 1500, 195, None)], "evaluated_mm": [9500, 0], "lamp_mm": 12000},
        ("under_gl", 12300): {"step_poles": [("straight", 12300, 75, None), ("taper", 9800, 195, 75), ("straight", 1800, 195, None)], "evaluated_mm": [9800, 0], "lamp_mm": 12300},
    },
    "LS": {
        ("on_gl", 8100): {"step_poles": [("taper", 8100, 165, 85)], "evaluated_mm": [0], "arm_mm": 8000, "arm_angles": (0,)},
        ("under_gl", 8400): {"step_poles": [("taper", 8400, 165, 85), ("straight", 300, 165, None)], "evaluated_mm": [0], "arm_mm": 8300, "arm_angles": (0,)},
        ("on_gl", 10100): {"step_poles": [("taper", 10100, 175, 75)], "evaluated_mm": [0], "arm_mm": 10000, "arm_angles": (0,)},
        ("under_gl", 10400): {"step_poles": [("taper", 10400, 175, 75), ("straight", 300, 175, None)], "evaluated_mm": [0], "arm_mm": 10300, "arm_angles": (0,)},
        ("on_gl", 12100): {"step_poles": [("taper", 12100, 195, 75)], "evaluated_mm": [0], "arm_mm": 12000, "arm_angles": (0,)},
        ("under_gl", 12400): {"step_poles": [("taper", 12400, 195, 75), ("straight", 300, 195, None)], "evaluated_mm": [0], "arm_mm": 12300, "arm_angles": (0,)},
    },
    "LA": {
        ("on_gl", 4600): {"step_poles": [("straight", 4600, 75, None), ("taper", 3505, 165, 75), ("straight", 1600, 165, None)], "evaluated_mm": [3505, 0], "arm_mm": 4500, "arm_angles": (0,)},
        ("under_gl", 4900): {"step_poles": [("straight", 4900, 75, None), ("taper", 3805, 165, 75), ("straight", 1900, 165, None)], "evaluated_mm": [3805, 0], "arm_mm": 4800, "arm_angles": (0,)},
        ("on_gl", 5100): {"step_poles": [("straight", 5100, 75, None), ("taper", 3505, 165, 75), ("straight", 1600, 165, None)], "evaluated_mm": [3505, 0], "arm_mm": 5000, "arm_angles": (0,)},
        ("under_gl", 5400): {"step_poles": [("straight", 5400, 75, None), ("taper", 3805, 165, 75), ("straight", 1900, 165, None)], "evaluated_mm": [3805, 0], "arm_mm": 5300, "arm_angles": (0,)},
        ("on_gl", 8100): {"step_poles": [("straight", 8100, 75, None), ("taper", 6600, 165, 75), ("straight", 1600, 165, None)], "evaluated_mm": [6600, 0], "arm_mm": 8000, "arm_angles": (0,)},
        ("under_gl", 8400): {"step_poles": [("straight", 8400, 75, None), ("taper", 6900, 165, 75), ("straight", 1900, 165, None)], "evaluated_mm": [6900, 0], "arm_mm": 8300, "arm_angles": (0,)},
        ("on_gl", 10100): {"step_poles": [("straight", 10100, 75, None), ("taper", 7600, 175, 75), ("straight", 1600, 175, None)], "evaluated_mm": [7600, 0], "arm_mm": 10000, "arm_angles": (0,)},
        ("under_gl", 10400): {"step_poles": [("straight", 10400, 75, None), ("taper", 7900, 175, 75), ("straight", 1900, 175, None)], "evaluated_mm": [7900, 0], "arm_mm": 10300, "arm_angles": (0,)},
        ("on_gl", 12100): {"step_poles": [("straight", 12100, 75, None), ("taper", 9600, 195, 75), ("straight", 1600, 195, None)], "evaluated_mm": [9600, 0], "arm_mm": 12000, "arm_angles": (0,)},
        ("under_gl", 12400): {"step_poles": [("straight", 12400, 75, None), ("taper", 9900, 195, 75), ("straight", 1900, 195, None)], "evaluated_mm": [9900, 0], "arm_mm": 12300, "arm_angles": (0,)},
    },
    "TS": {
        ("on_gl", 8100): {"step_poles": [("taper", 8100, 165, 85)], "evaluated_mm": [0], "arm_mm": 8000, "arm_angles": (0, 180)},
        ("under_gl", 8400): {"step_poles": [("taper", 8400, 165, 85), ("straight", 300, 165, None)], "evaluated_mm": [0], "arm_mm": 8300, "arm_angles": (0, 180)},
        ("on_gl", 10100): {"step_poles": [("taper", 10100, 175, 75)], "evaluated_mm": [0], "arm_mm": 10000, "arm_angles": (0, 180)},
        ("under_gl", 10400): {"step_poles": [("taper", 10400, 175, 75), ("straight", 300, 175, None)], "evaluated_mm": [0], "arm_mm": 10300, "arm_angles": (0, 180)},
        ("on_gl", 12100): {"step_poles": [("taper", 12100, 195, 75)], "evaluated_mm": [0], "arm_mm": 12000, "arm_angles": (0, 180)},
        ("under_gl", 12400): {"step_poles": [("taper", 12400, 195, 75), ("straight", 300, 195, None)], "evaluated_mm": [0], "arm_mm": 12300, "arm_angles": (0, 180)},
    },
    "TA": {
        ("on_gl", 8100): {"step_poles": [("straight", 8100, 75, None), ("taper", 6600, 165, 75), ("straight", 1600, 165, None)], "evaluated_mm": [6600, 0], "arm_mm": 8000, "arm_angles": (0, 180)},
        ("under_gl", 8400): {"step_poles": [("straight", 8400, 75, None), ("taper", 6900, 165, 75), ("straight", 1900, 165, None)], "evaluated_mm": [6900, 0], "arm_mm": 8300, "arm_angles": (0, 180)},
        ("on_gl", 10100): {"step_poles": [("straight", 10100, 75, None), ("taper", 7600, 175, 75), ("straight", 1600, 175, None)], "evaluated_mm": [7600, 0], "arm_mm": 10000, "arm_angles": (0, 180)},
        ("under_gl", 10400): {"step_poles": [("straight", 10400, 75, None), ("taper", 7900, 175, 75), ("straight", 1900, 175, None)], "evaluated_mm": [7900, 0], "arm_mm": 10300, "arm_angles": (0, 180)},
        ("on_gl", 12100): {"step_poles": [("straight", 12100, 75, None), ("taper", 9600, 195, 75), ("straight", 1600, 195, None)], "evaluated_mm": [9600, 0], "arm_mm": 12000, "arm_angles": (0, 180)},
        ("under_gl", 12400): {"step_poles": [("straight", 12400, 75, None), ("taper", 9900, 195, 75), ("straight", 1900, 195, None)], "evaluated_mm": [9900, 0], "arm_mm": 12300, "arm_angles": (0, 180)},
    },
}
TAPER_THICKNESS_MM = 4
TAPER_GEOMETRY_MATERIAL = "STK400"
UNDER_GL_EMBEDDED_M = Decimal("0.3")
# Lampu tipe I, berdiri sendiri di tiang
TAPER_LAMP = {
    "name": "灯具",
    "front_area_m2": Decimal("0.1"),
    "mass_per_unit_kg": Decimal("14"),
    "base_wind_coefficient": Decimal("1"),
    "quantity": 1,
}
# Lengan tipe L dan T, material STK400 (TAPER_GEOMETRY_MATERIAL), sama dengan payload.
TAPER_ARM_NAMES = ("照明アーム1", "照明アーム2")
TAPER_ARM = {
    "diameter_mm": Decimal("60.5"),
    "thickness_mm": Decimal("3.8"),
    "total_length_m": Decimal("0.18"),
    "exposed_length_m": Decimal("0.18"),
}
# Lampu yang sama, dipasang di ujung lengan. Luas samping Omni dipakai torsi lengan.
TAPER_ARM_LAMP = {**TAPER_LAMP, "side_area_m2": Decimal("0.1"), "horizontal_load_distance_m": Decimal("0.18")}


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
# West: bushing hanya bila nilai bukan 0, terminal_cap hanya bila 0, nipple tidak pernah.
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
                    default_air_density = standard.get("defaultAirDensity"),
                    default_horizontal_acceleration = standard.get("defaultHorizontalAcceleration"),
                    default_response_ratio = standard.get("defaultResponseRatio"),
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
def _mm_to_m(value_mm: int) -> Decimal:
    return Decimal(value_mm) / 1000


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

        for (ground_position_name, height_mm), row in rows.items():
            ground_position = PoleHeightGroundPosition(ground_position_name)

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
                is_under_gl = ground_position == PoleHeightGroundPosition.under_gl
                height.gl_elevation_m = UNDER_GL_EMBEDDED_M if is_under_gl else Decimal("0")
            if height.evaluated_positions_m is None:
                height.evaluated_positions_m = [_mm_to_m(value) for value in row["evaluated_mm"]]

            # Idempotent per pilihan tinggi: tiap kelompok hanya dibuat bila belum ada sama sekali.
            has_step_poles = (await db.execute(
                select(PoleStandardStepPole.id).where(
                    PoleStandardStepPole.pole_standard_height_id == height.id
                ).limit(1)
            )).scalar_one_or_none()
            if has_step_poles is None:
                for number, (kind, top_mm, diameter_lower, diameter_upper) in enumerate(row["step_poles"], start=1):
                    is_taper = kind == PoleType.taper.value
                    db.add(PoleStandardStepPole(
                        pole_standard_height_id=height.id,
                        material_id=material.id,
                        name=f"Pole-{number}",
                        pole_type=PoleType(kind),
                        top_elevation_m=_mm_to_m(top_mm),
                        diameter_lower_mm=diameter_lower,
                        diameter_upper_mm=diameter_upper,
                        thickness_lower_mm=TAPER_THICKNESS_MM,
                        thickness_upper_mm=TAPER_THICKNESS_MM if is_taper else None,
                    ))

            if "lamp_mm" in row:
                has_objects = (await db.execute(
                    select(PoleStandardDirectObject.id).where(
                        PoleStandardDirectObject.pole_standard_height_id == height.id
                    ).limit(1)
                )).scalar_one_or_none()
                if has_objects is None:
                    db.add(PoleStandardDirectObject(
                        pole_standard_height_id=height.id,
                        object_kind=ObjectKind.omni,
                        elevation_m=_mm_to_m(row["lamp_mm"]),
                        **TAPER_LAMP,
                    ))

            if "arm_mm" in row:
                has_arms = (await db.execute(
                    select(PoleStandardArm.id).where(
                        PoleStandardArm.pole_standard_height_id == height.id
                    ).limit(1)
                )).scalar_one_or_none()
                if has_arms is None:
                    for name, angle in zip(TAPER_ARM_NAMES, row["arm_angles"]):
                        db.add(PoleStandardArm(
                            pole_standard_height_id=height.id,
                            material_id=material.id,
                            name=name,
                            installation_height_m=_mm_to_m(row["arm_mm"]),
                            fixed_angle_deg=angle,
                            arm_objects=[PoleStandardArmObject(object_kind=ObjectKind.omni, **TAPER_ARM_LAMP)],
                            **TAPER_ARM,
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
