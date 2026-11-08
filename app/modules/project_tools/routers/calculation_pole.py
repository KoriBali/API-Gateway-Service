"""Project Tools calculation pole: Hitung dan preview laporan tanpa request dan tanpa
menyimpan apa pun, lalu Simpan satu alur ke request yang sudah ada atau request baru.

"pole" = perhitungan primary (tiang). Perhitungan secondary kelak memakai path sendiri.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.database.models.calculation import CalculationRun, PoleKind
from app.database.models.workflow import WorkType
from app.modules.assignment import permissions as assignment_permissions
from app.modules.assignment.repository import AssignmentRepository
from app.modules.calculation import builder, report
from app.modules.calculation.repository import CalculationCaseRepository
from app.modules.calculation.routers.runs import (
    calculate_on_engine,
    catalog_pole_request,
    ensure_calculable,
    validate_pole_input,
)
from app.modules.calculation.schemas import CalculateResult
from app.modules.case import permissions as case_permissions
from app.modules.intake.repository import RequestRepository
from app.modules.intake.routers.requests import validate_create_payload
from app.modules.intake.schemas import CalculationConditionsCreate
from app.modules.project_tools import permissions
from app.modules.project_tools.repository import ProjectToolRepository, catalog_shape
from app.modules.project_tools.schemas import PoleToolSave, PoleToolSaveResult, PoleToolSession
from app.utils.response import success_response

routerPoleTool = APIRouter(prefix="/api/project-tools/calculation/pole", tags=["Project Tools"])

# Hitung dan preview: semua peran. Simpan: hanya pengerja (reviewer dan superadmin tidak
# pernah di-assign, superadmin juga tanpa department).
_TOOL_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter", "yoshimoto_reviewer")
_SAVE_ROLE = require_roles("admin_department", "drafter_checker", "drafter")



# ===== Helper =====
async def _prepare(db: AsyncSession, payload: PoleToolSession):
    """Validasi sesi tool dan payload engine. Sama untuk Hitung, preview, dan Simpan."""
    if not await RequestRepository.design_standard_exists(db, payload.conditions.design_standard_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="designStandardId does not reference an existing design standard",
        )
    height, ground_position = await validate_pole_input(db, payload.input)
    design_standard = await CalculationCaseRepository.get_design_standard(db, payload.conditions.design_standard_id)
    ensure_calculable(payload.conditions, design_standard, height)
    engine_request = await catalog_pole_request(
        db, conditions=payload.conditions, design_standard=design_standard, height=height, payload=payload.input,
    )
    return height, ground_position, design_standard, engine_request


def _input_snapshot(payload: PoleToolSession, engine_request: dict, design_standard, height, ground_position) -> dict:
    """Bentuk input_snapshot run, sama dengan Simpan case."""
    return {
        "engine_request": engine_request,
        "context": builder.build_context(
            conditions=payload.conditions, design_standard=design_standard, height=height,
            ground_position=ground_position, embedment_length_mm=payload.input.embedment_length_mm,
        ),
    }


async def _load_target(db: AsyncSession, actor: CurrentUser, request_id: str, payload: PoleToolSave, *, for_update: bool):
    """Request tujuan yang sudah ada beserta conditions calculation-nya. Diperiksa dua kali:
    sebelum Hitung (tanpa kunci) dan sesudah baris request dikunci, karena status dan
    conditions bisa berubah selama Calculation Service menghitung."""
    req = await case_permissions.load_readable_request(db, request_id, actor, for_update=for_update)
    permissions.ensure_can_save_to(actor, req, WorkType.calculation)
    existing = await RequestRepository.get_conditions(db, WorkType.calculation, req.id)
    permissions.ensure_calculation_conditions_match(existing, payload.conditions)
    return req, existing



# ===== Hitung =====
@routerPoleTool.post("/calculate")
async def calculate_pole(
    payload: PoleToolSession,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_TOOL_ROLE),
):
    _, _, _, engine_request = await _prepare(db, payload)
    run_status, _, _, result_display = await calculate_on_engine(engine_request, f"pole tool by {actor.id}")
    return success_response(
        data=CalculateResult(status=run_status, display=result_display),
        message="Calculation completed",
    )



# ===== Preview laporan =====
@routerPoleTool.post("/report")
async def preview_pole_report(
    payload: PoleToolSession,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_TOOL_ROLE),
):
    height, ground_position, design_standard, engine_request = await _prepare(db, payload)
    run_status, _, result_body, _ = await calculate_on_engine(engine_request, f"pole tool by {actor.id}")
    # Run sementara, tidak pernah ditambahkan ke sesi: formatter laporan membaca bentuk run.
    preview_run = CalculationRun(
        status=run_status,
        input_snapshot=_input_snapshot(payload, engine_request, design_standard, height, ground_position),
        result_snapshot=result_body,
    )
    try:
        data = report.format_report(preview_run)
    except report.ReportTemplateUnavailable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "report_template_unavailable",
                "message": "The design standard has no report template yet",
            },
        )
    # runId dan header null: belum ada run, header diisi sesudah Simpan.
    return success_response(data=data, message="Calculation report preview")



# ===== Simpan satu alur =====
@routerPoleTool.post("/save")
async def save_pole(
    payload: PoleToolSave,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_SAVE_ROLE),
):
    # Periksa dulu, tanpa kunci.
    if payload.new_request is not None:
        await validate_create_payload(db, actor, payload.new_request)
    else:
        await _load_target(db, actor, payload.request_id, payload, for_update=False)
    height, ground_position, design_standard, engine_request = await _prepare(db, payload)
    expected_catalog = catalog_shape(height, height.step_poles)

    # Hitung, tanpa kunci. Gagal = tidak ada yang tersimpan (422 / 503).
    run_status, utilization_ratio, result_body, _ = await calculate_on_engine(
        engine_request, f"pole tool save by {actor.id}",
    )

    # Tulis dalam SATU transaksi. Repository dipanggil commit=False; create_run
    # di akhir yang commit. Penolakan di bagian ini membuang semua tulisan (sesi ditutup
    # tanpa commit).
    request_created = payload.new_request is not None
    if request_created:
        await assignment_permissions.ensure_assignable(
            db, department_id=actor.department_id, design_type=payload.new_request.design_type,
            assignee_user_id=actor.id, work_type=WorkType.calculation,
        )
        req = await RequestRepository.create(
            db, payload.new_request,
            created_by_user_id=actor.id,
            responsible_department_id=actor.department_id,
            assignments=[(actor.id, WorkType.calculation)],
            commit=False,
        )
        existing_conditions, assignment_created = None, True
    else:
        req, existing_conditions = await _load_target(db, actor, payload.request_id, payload, for_update=True)
        assignment_created = not await AssignmentRepository.has_active(db, req.id, actor.id, WorkType.calculation)
        if assignment_created:
            await assignment_permissions.ensure_assignable(
                db, department_id=req.responsible_department_id, design_type=req.design_type,
                assignee_user_id=actor.id, work_type=WorkType.calculation,
            )
            await AssignmentRepository.create(
                db, request_id=req.id, assignee_user_id=actor.id, work_type=WorkType.calculation,
                assigned_by_user_id=actor.id, commit=False,
            )

    conditions_created = existing_conditions is None
    if conditions_created:
        await RequestRepository.create_conditions(
            db, WorkType.calculation, req,
            CalculationConditionsCreate(**payload.conditions.model_dump()), commit=False,
        )

    title = payload.case.title or req.subject
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="title is required because the request has no subject",
        )
    case = await CalculationCaseRepository.create(
        db, req, owner_user_id=actor.id,
        data={"title": title, "case_label": payload.case.case_label, "pole_kind": PoleKind.standard},
        commit=False,
    )
    await CalculationCaseRepository.save_input(db, case, height, payload.input, ground_position, commit=False)

    # Katalog harus sama dengan yang dipakai menghitung di atas (run = yang dilihat user).
    if await ProjectToolRepository.fresh_catalog_shape(db, height.id) != expected_catalog:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "catalog_changed",
                "message": "The pole catalog changed after the calculation; calculate and save again",
            },
        )

    request_id, case_id = req.id, case.id
    run = await CalculationCaseRepository.create_run(
        db, case_id=case_id, run_by_user_id=actor.id, status=run_status,
        utilization_ratio=utilization_ratio,
        input_snapshot=_input_snapshot(payload, engine_request, design_standard, height, ground_position),
        result_snapshot=result_body, error_snapshot=None,
    )  # commit: menutup seluruh transaksi Simpan

    saved = await RequestRepository.get_by_id(db, request_id)
    return success_response(
        data=PoleToolSaveResult(
            request_id=request_id,
            request_created=request_created,
            request_status=saved.status,
            assignment_created=assignment_created,
            conditions_created=conditions_created,
            case_id=case_id,
            run_id=run.id,
            run_status=run.status,
        ),
        status_code=status.HTTP_201_CREATED,
        message="Project tool saved to request",
    )
