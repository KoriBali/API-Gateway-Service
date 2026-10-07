"""
File ini untuk inisiasi Data awal (seeding) Data Request (intake).

Prasyarat (jalankan lebih dulu):
    python -m app.scripts.seed_master     # pole_categories, design_standards, regions, materials
    python -m app.scripts.seed_identity   # user + department

How to Run(pipenv shell):
    python -m app.scripts.seed_request

Catatan desain:
- Data contoh fiktif untuk uji scope dan intake, bukan data pesanan nyata.
- responsible_department_id SELALU mengikuti department si pembuat (created_by_user),
  sesuai aturan create_request di router (department dikunci ke pembuat).
- Setiap request lahir lengkap seperti di endpoint intake: ekstensi form sesuai
  brand_line, request_design_conditions, request_finish, dan conditions.
- Request YP selalu membawa document_no (図番), sesuai aturan form intake YP.
- Idempotent: project di-skip bila identitasnya (request_form, scope_code, pj_no)
  sudah ada; request di-skip bila (created_by_user_id, request_no) sudah ada.
"""
import asyncio
from datetime import date, timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.database.models.identity import User
from app.database.models.intake import (
    BrandLine,
    DatabankProject,
    Request,
    RequestType,
    DesignType,
    RequestClassification,
    PoleKind,
    RequestYpDetails,
    RequestYsDetails,
    RequestDesignCondition,
    RequestFinish,
)
from app.database.models.calculation import Condition
from app.database.models.calculation_object import FoundationType
from app.database.models.drawing import DrawingType, SurfaceTreatmentOption, PlatingType, PaintingType
from app.database.models.master import PoleCategory, DesignStandard, Material


_TODAY = date.today()


def _due(days: int | None) -> date | None:
    return None if days is None else _TODAY + timedelta(days=days)


# (request_form, scope_code, pj_no). YS selalu scope_code kosong.
PROJECTS = [
    (BrandLine.yp, "E", "100001"),
    (BrandLine.yp, "E", "100002"),
    (BrandLine.ys, "", "20001"),
]

# creator = username pembuat; pole_category = nama kategori; design_standard = nama
# standar di kategori itu (lihat seed_master). project = indeks PROJECTS atau None
# (request berkepala General Affairs, tanpa project). design_conditions.material =
# nama di master materials (diubah jadi material_id).
REQUESTS = [
    # budi (drafter/YSG)
    {
        "creator": "budi", "project": 0, "brand_line": BrandLine.yp,
        "pole_category": "lighting-pole", "design_standard": "JIL",
        "request_no": "REQ-2026-001", "receipt_no": "RCP-001", "pj_no": "100001",
        "request_type": RequestType.general, "design_type": DesignType.drawing,
        "request_classification": RequestClassification.new, "pole_kind": PoleKind.standard,
        "subject": "Sample lighting pole A", "due_in_days": 14,
        "wind_speed": 60, "air_density": 1.23,
        "yp_details": {
            "document_no": "EPJ100001-1", "tail_code": "PJ", "record_no": "1",
            "brand_mark": BrandLine.yp, "drafting_design": True,
        },
        "design_conditions": {
            "material_text": "STK400", "material": "STK400",
            "foundation_type": FoundationType.square,
            "foundation_width_x": 800, "foundation_width_y": 800, "embedment_depth": 1500,
            "drawing_type": DrawingType.approval,
        },
        "finish": {"treatment_option": SurfaceTreatmentOption.plating_only, "plating_type": PlatingType.standard},
    },
    {
        # tail YS di request form YP: tail mengikuti merek, bukan form; project tetap sama
        "creator": "budi", "project": 0, "brand_line": BrandLine.yp,
        "pole_category": "acemast", "design_standard": "V60",
        "request_no": "REQ-2026-002", "receipt_no": "RCP-002", "pj_no": "100001",
        "request_type": RequestType.special, "design_type": DesignType.calculation,
        "request_classification": RequestClassification.change, "pole_kind": PoleKind.custom,
        "subject": "Sample acemast change", "due_in_days": 30,
        "wind_speed": None, "air_density": 1.23,
        "yp_details": {
            "document_no": "EYS100001-2", "tail_code": "YS", "record_no": "2",
            "brand_mark": BrandLine.ys, "calc_strength": True, "has_competitor": False,
        },
    },
    # andi (drafter/YSG) -> menguji isolasi antar-drafter dalam department yang sama
    {
        "creator": "andi", "project": 1, "brand_line": BrandLine.yp,
        "pole_category": "signboard", "design_standard": "V60",
        "request_no": "REQ-2026-003", "receipt_no": None, "pj_no": "100002",
        "request_type": RequestType.general, "design_type": DesignType.drawing_calculation,
        "request_classification": RequestClassification.reuse_new, "pole_kind": PoleKind.standard,
        "subject": None, "due_in_days": 7,
        "wind_speed": 34, "air_density": 1.22,
        "yp_details": {"document_no": "EPJ100002"},   # tanpa seq, segmen lain kosong
    },
    # dewi (drafter/YSC) -> department berbeda, menguji scope lintas-department
    {
        "creator": "dewi", "project": 2, "brand_line": BrandLine.ys,
        "pole_category": "lighting-pole", "design_standard": "JIL",
        "request_no": "REQ-2026-004", "receipt_no": "RCP-004", "pj_no": "20001",
        "request_type": RequestType.special, "design_type": DesignType.calculation,
        "request_classification": RequestClassification.new, "pole_kind": PoleKind.custom,
        "subject": "Sample YS pole", "due_in_days": 21,
        "wind_speed": 40, "air_density": 1.23,
        "ys_details": {"delivery_quantity": 3},
        "design_conditions": {
            "drawing_type": DrawingType.manufacturer, "design_standard_text": "未定",
            "opening_height": "GL+750", "concrete_strength": "Fc24", "opening_direction_note": "A",
        },
        "finish": {
            "treatment_option": SurfaceTreatmentOption.plating_painting,
            "painting_type": PaintingType.urethane, "color_name": "Sample grey",
        },
    },
    {
        # semua field opsional kosong, tanpa project -> menguji nullable
        "creator": "dewi", "project": None, "brand_line": BrandLine.ys,
        "pole_category": "multiple", "design_standard": "V60",
        "request_no": "REQ-2026-005", "receipt_no": None, "pj_no": "20002",
        "request_type": RequestType.general, "design_type": DesignType.drawing,
        "request_classification": RequestClassification.new, "pole_kind": None,
        "subject": None, "due_in_days": None,
        "wind_speed": None, "air_density": 1.23,
        "ys_details": {},
    },
    # eko (drafter/YSF)
    {
        "creator": "eko", "project": None, "brand_line": BrandLine.yp,
        "pole_category": "acemast", "design_standard": "V60",
        "request_no": "REQ-2026-006", "receipt_no": "RCP-006", "pj_no": "100003",
        "request_type": RequestType.general, "design_type": DesignType.calculation,
        "request_classification": RequestClassification.new, "pole_kind": PoleKind.standard,
        "subject": "Sample general affairs request", "due_in_days": 45,
        "wind_speed": None, "air_density": 1.23,
        "yp_details": {"document_no": "EPJ100003-1", "tail_code": "PJ", "record_no": "1"},
    },
]


async def _seed_projects(db) -> list[DatabankProject]:
    projects = []
    for request_form, scope_code, pj_no in PROJECTS:
        project = await db.scalar(
            select(DatabankProject).where(
                DatabankProject.request_form == request_form,
                DatabankProject.scope_code == scope_code,
                DatabankProject.pj_no == pj_no,
                DatabankProject.is_placeholder.is_(False),
            )
        )
        if project is None:
            project = DatabankProject(
                request_form=request_form, scope_code=scope_code, pj_no=pj_no, is_placeholder=False,
            )
            db.add(project)
            await db.flush()  # butuh project.id untuk request
        projects.append(project)
    return projects


async def _design_standard_id(db, category_name: str, standard_name: str) -> tuple[str, str]:
    row = (await db.execute(
        select(PoleCategory.id, DesignStandard.id)
        .join(DesignStandard, DesignStandard.pole_category_id == PoleCategory.id)
        .where(PoleCategory.name == category_name, DesignStandard.name == standard_name)
    )).first()
    if row is None:
        raise ValueError(
            f"Design standard '{standard_name}' di kategori '{category_name}' tidak ada. "
            "Jalankan seed_master dulu."
        )
    return row[0], row[1]


async def _design_conditions(db, spec: dict) -> dict:
    """Salin dict spec, lalu ganti nama material menjadi material_id."""
    data = dict(spec)
    material_name = data.pop("material", None)
    if material_name is not None:
        material_id = await db.scalar(select(Material.id).where(Material.name == material_name))
        if material_id is None:
            raise ValueError(f"Material '{material_name}' tidak ada. Jalankan seed_master dulu.")
        data["material_id"] = material_id
    return data


async def _seed_requests(db, projects: list[DatabankProject]) -> int:
    users = {u.username: u for u in (await db.execute(select(User))).scalars().all()}
    created = 0
    for spec in REQUESTS:
        user = users.get(spec["creator"])
        if user is None:
            raise ValueError(f"User '{spec['creator']}' tidak ada. Jalankan seed_identity dulu.")
        if user.department_id is None:
            raise ValueError(
                f"User '{spec['creator']}' tidak punya department; tidak bisa jadi pembuat request."
            )

        exists = await db.scalar(
            select(Request.id).where(
                Request.created_by_user_id == user.id,
                Request.request_no == spec["request_no"],
            )
        )
        if exists is not None:
            continue

        category_id, design_standard_id = await _design_standard_id(
            db, spec["pole_category"], spec["design_standard"]
        )
        project = projects[spec["project"]] if spec["project"] is not None else None

        req = Request(
            brand_line=spec["brand_line"],
            project_id=project.id if project is not None else None,
            responsible_department_id=user.department_id,
            created_by_user_id=user.id,
            pole_category_id=category_id,
            request_no=spec["request_no"],
            receipt_no=spec["receipt_no"],
            pj_no=spec["pj_no"],
            request_type=spec["request_type"],
            design_type=spec["design_type"],
            request_classification=spec["request_classification"],
            pole_kind=spec["pole_kind"],
            subject=spec["subject"],
            due_date=_due(spec["due_in_days"]),
        )
        db.add(req)
        await db.flush()  # butuh req.id untuk baris anak

        if spec["brand_line"] == BrandLine.yp:
            db.add(RequestYpDetails(request_id=req.id, brand_line=BrandLine.yp, **spec["yp_details"]))
        else:
            db.add(RequestYsDetails(request_id=req.id, brand_line=BrandLine.ys, **spec.get("ys_details", {})))
        db.add(RequestDesignCondition(
            request_id=req.id, **await _design_conditions(db, spec.get("design_conditions", {})),
        ))
        db.add(RequestFinish(request_id=req.id, **spec.get("finish", {})))
        db.add(Condition(
            request_id=req.id,
            design_standard_id=design_standard_id,
            wind_speed=spec["wind_speed"],
            air_density=spec["air_density"],
        ))
        created += 1
    return created


async def main():
    async with AsyncSessionLocal() as db:
        projects = await _seed_projects(db)
        created = await _seed_requests(db, projects)
        await db.commit()
    print(f"Seed request selesai. Project: {len(projects)} tersedia, Request: {created} dibuat.")


if __name__ == "__main__":
    asyncio.run(main())