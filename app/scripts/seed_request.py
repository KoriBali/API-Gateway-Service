"""
File ini untuk inisiasi Data awal (seeding) Data Request (intake)

Prasyarat (jalankan lebih dulu):
    python -m app.scripts.seed_master     # pole_categories, design_standards, regions, materials
    python -m app.scripts.seed_identity   # user + department

How to Run(pipenv shell):
    python -m app.scripts.seed_request

Catatan desain:
- Data contoh fiktif untuk uji scope dan intake, bukan data pesanan nyata.
- responsible_department_id SELALU mengikuti department si pembuat (created_by_user),
  sesuai aturan create_request di router (department dikunci ke pembuat).
- Setiap request lahir lengkap seperti di endpoint intake: request_shared_details,
  ekstensi form sesuai brand_line, request_finish, dan conditions.
- Setiap request mematuhi aturan form intake yang ditegakkan API: request_no, subject,
  request_date, due_date, requesting_department_name terisi; request YP mengisi
  requesting_department_code; request yang memuat drawing mengisi region dan drawing_type.
- request_no YP = 図番 utuh (mis. EPJ100001-1), request_no YS = 依頼No (mis. YSE-26-0001).
- Setiap request lahir dengan assignment aktif (DD invariant intake 3), seperti endpoint
  intake: pembuat (drafter) di-assign ke semua work type di design_type, kecuali spec
  menyebut "assignments" sendiri. Assignment hanya dibuat bersama request baru; request
  lama yang di-skip tidak ditambahi assignment.
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
    RequestSharedDetails,
    RequestYpDetails,
    RequestYsDetails,
    RequestFinish,
)
from app.database.models.calculation import Condition
from app.database.models.calculation_object import FoundationType
from app.database.models.drawing import DrawingType, SurfaceTreatmentOption, PlatingType, PaintingType
from app.database.models.master import PoleCategory, DesignStandard, Material, Region
from app.database.models.workflow import AssignmentStatus, RequestAssignment, WorkType
from app.modules.assignment.permissions import WORK_TYPES_OF


_TODAY = date.today()
_REQUEST_DATE = _TODAY - timedelta(days=3)


def _due(days: int) -> date:
    return _TODAY + timedelta(days=days)


# (request_form, scope_code, pj_no). YS selalu scope_code kosong.
PROJECTS = [
    (BrandLine.yp, "E", "100001"),
    (BrandLine.yp, "E", "100002"),
    (BrandLine.ys, "", "20001"),
]

# creator = username pembuat; pole_category = nama kategori; design_standard = nama
# standar di kategori itu (lihat seed_master). project = indeks PROJECTS atau None
# (request berkepala General Affairs, tanpa project). shared_details.region = kode di
# master regions (diubah jadi region_id); ys_details.material = nama di master materials
# (diubah jadi material_id). assignments = daftar (username, work type); bila tidak ada,
# pembuat di-assign ke semua work type di design_type.
REQUESTS = [
    # budi (drafter/YSG)
    {
        "creator": "budi", "project": 0, "brand_line": BrandLine.yp,
        "pole_category": "lighting-pole", "design_standard": "JIL",
        "request_no": "EPJ100001-1", "pj_no": "100001",
        "request_type": RequestType.general, "design_type": DesignType.drawing,
        "request_classification": RequestClassification.new,
        "subject": "Sample lighting pole A", "due_in_days": 14,
        "requesting_department_name": "Sample East Office",
        "wind_speed": 60, "air_density": 1.23,
        "shared_details": {
            "scheduled_delivery_date": "3/末", "delivery_quantity": 2,
            "requester_pic_name": "Sample PIC", "region": "east_japan",
            "drawing_type": DrawingType.approval, "paper_size": "A3",
            "is_cad_data_requested": True, "cad_format": "DXF",
        },
        "yp_details": {
            "requesting_department_code": "E", "tail_code": "PJ", "record_no": "1",
            "brand_mark": BrandLine.yp, "drafting_design": True,
            "schedule_flexibility": "Adjustable", "paper_frame": "YP Frame",
        },
        "finish": {"treatment_option": SurfaceTreatmentOption.plating_only, "plating_type": PlatingType.standard},
    },
    {
        # tail YS di request form YP: tail mengikuti merek, bukan form; project tetap sama
        "creator": "budi", "project": 0, "brand_line": BrandLine.yp,
        "pole_category": "acemast", "design_standard": "V60",
        "request_no": "EYS100001-2", "pj_no": "100001",
        "request_type": RequestType.general, "design_type": DesignType.calculation,
        "request_classification": RequestClassification.change,
        "subject": "Sample acemast change", "due_in_days": 30,
        "requesting_department_name": "Sample East Office",
        "wind_speed": None, "air_density": 1.23,
        "yp_details": {
            "requesting_department_code": "E", "tail_code": "YS", "record_no": "2",
            "brand_mark": BrandLine.ys, "calc_strength": True, "has_competitor": False,
        },
    },
    # andi (drafter/YSG) -> menguji isolasi antar-drafter dalam department yang sama
    {
        "creator": "andi", "project": 1, "brand_line": BrandLine.yp,
        "pole_category": "signboard", "design_standard": "V60",
        "request_no": "EPJ100002", "pj_no": "100002",   # 図番 tanpa seq
        "request_type": RequestType.general, "design_type": DesignType.drawing_calculation,
        "request_classification": RequestClassification.reuse_new,
        "subject": "Sample signboard reuse", "due_in_days": 7,
        "requesting_department_name": "Sample East Office",
        "wind_speed": 34, "air_density": 1.22,
        "shared_details": {"region": "west_japan", "drawing_type": DrawingType.meeting},
        "yp_details": {"requesting_department_code": "E"},   # segmen lain kosong
        # andi menghitung, budi (partner satu department) menggambar
        "assignments": [("andi", WorkType.calculation), ("budi", WorkType.drawing)],
    },
    # dewi (drafter/YSC) -> department berbeda, menguji scope lintas-department
    {
        "creator": "dewi", "project": 2, "brand_line": BrandLine.ys,
        "pole_category": "lighting-pole", "design_standard": "JIL",
        "request_no": "YSE-26-0001", "pj_no": "20001",
        "request_type": RequestType.general, "design_type": DesignType.calculation,
        "request_classification": RequestClassification.new,
        "subject": "Sample YS pole", "due_in_days": 21,
        "requesting_department_name": "Sample YS Company",
        "wind_speed": 40, "air_density": 1.23,
        "shared_details": {
            "scheduled_delivery_date": "2026/11/30", "delivery_quantity": 3,
            "is_cad_data_requested": False,
        },
        "ys_details": {
            "receipt_no": "26-0034",
            "material_text": "STK400", "material": "STK400",
            "foundation_type": FoundationType.square,
            "foundation_width_x": 800, "foundation_width_y": 800, "embedment_depth": 1500,
            "design_standard_text": "未定", "opening_height": "GL+750",
            "concrete_strength": "Fc24", "opening_direction_note": "A",
        },
        "finish": {
            "treatment_option": SurfaceTreatmentOption.plating_painting,
            "painting_type": PaintingType.urethane, "color_name": "Sample grey",
        },
    },
    {
        # hanya kolom wajib, tanpa project -> menguji nullable di tabel tambahan
        "creator": "dewi", "project": None, "brand_line": BrandLine.ys,
        "pole_category": "multiple", "design_standard": "V60",
        "request_no": "YSE-26-0002", "pj_no": "20002",
        "request_type": RequestType.special, "design_type": DesignType.calculation,
        "request_classification": RequestClassification.new,
        "subject": "Sample YS minimal", "due_in_days": 60,
        "requesting_department_name": "Sample YS Company",
        "wind_speed": None, "air_density": 1.23,
    },
    # eko (drafter/YSF)
    {
        # request berkepala General Affairs (総務部): request_type special, tanpa project
        "creator": "eko", "project": None, "brand_line": BrandLine.yp,
        "pole_category": "acemast", "design_standard": "V60",
        "request_no": "EPJ100003-1", "pj_no": "100003",
        "request_type": RequestType.special, "design_type": DesignType.calculation,
        "request_classification": RequestClassification.new,
        "subject": "Sample general affairs request", "due_in_days": 45,
        "requesting_department_name": "Sample General Affairs",
        "wind_speed": None, "air_density": 1.23,
        "yp_details": {"requesting_department_code": "E", "tail_code": "PJ", "record_no": "1"},
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


async def _shared_details(db, spec: dict) -> dict:
    """Salin dict spec, lalu ganti kode region menjadi region_id."""
    data = dict(spec)
    region_code = data.pop("region", None)
    if region_code is not None:
        region_id = await db.scalar(select(Region.id).where(Region.code == region_code))
        if region_id is None:
            raise ValueError(f"Region '{region_code}' tidak ada. Jalankan seed_master dulu.")
        data["region_id"] = region_id
    return data


async def _ys_details(db, spec: dict) -> dict:
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
            pj_no=spec["pj_no"],
            request_type=spec["request_type"],
            design_type=spec["design_type"],
            request_classification=spec["request_classification"],
            subject=spec["subject"],
            request_date=_REQUEST_DATE,
            due_date=_due(spec["due_in_days"]),
            requesting_department_name=spec["requesting_department_name"],
        )
        db.add(req)
        await db.flush()  # butuh req.id untuk baris anak

        db.add(RequestSharedDetails(
            request_id=req.id, **await _shared_details(db, spec.get("shared_details", {})),
        ))
        if spec["brand_line"] == BrandLine.yp:
            db.add(RequestYpDetails(request_id=req.id, brand_line=BrandLine.yp, **spec["yp_details"]))
        else:
            db.add(RequestYsDetails(
                request_id=req.id, brand_line=BrandLine.ys, **await _ys_details(db, spec.get("ys_details", {})),
            ))
        db.add(RequestFinish(request_id=req.id, **spec.get("finish", {})))
        db.add(Condition(
            request_id=req.id,
            design_standard_id=design_standard_id,
            wind_speed=spec["wind_speed"],
            air_density=spec["air_density"],
        ))
        assignments = spec.get("assignments") or [
            (spec["creator"], wt) for wt in WORK_TYPES_OF[spec["design_type"]]
        ]
        for username, work_type in assignments:
            assignee = users.get(username)
            if assignee is None or assignee.department_id != user.department_id:
                raise ValueError(f"Assignee '{username}' tidak ada atau beda department dengan pembuat.")
            db.add(RequestAssignment(
                request_id=req.id,
                assignee_user_id=assignee.id,
                assigned_by_user_id=user.id,
                work_type=work_type,
                assignment_status=AssignmentStatus.active,
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