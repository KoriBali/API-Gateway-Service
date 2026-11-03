from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake.repository import RequestRepository
from app.modules.case import permissions as case_permissions
from app.modules.calculation import builder, display, report
from app.modules.calculation.repository import CalculationCaseRepository, ReportHeaderRepository
from app.modules.calculation.routers.cases import case_detail
from app.modules.calculation.schemas import (
    CalculateResult,
    CalculationInput,
    CalculationRunRead,
    CalculationRunSummary,
    CalculationSaveResult,
    ReportHeaderRead,
    RunNotCreated,
)
from app.services.calculation import POLE_CALCULATE_PATH, EngineUnavailable, post_engine
from app.database.models.calculation import PoleKind, StatusCalculationRun
from app.database.models.master import PoleStandardType
from app.database.models.workflow import WorkType

routerCalculationRun = APIRouter(prefix="/api/requests", tags=["Calculation"])

_READ_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")
# Hitung: semua peran pengerja yang boleh membaca case, tidak harus owner.
_WORKER_ROLE = require_roles("admin_department", "drafter_checker", "drafter")



# ===== Helper =====
async def _load_case(db: AsyncSession, request_id: str, case_id: str, actor: CurrentUser, *, for_update: bool = False):
    await case_permissions.load_readable_request(db, request_id, actor)
    case = await CalculationCaseRepository.get_in_request(db, request_id, case_id, for_update=for_update)
    if case is None:
        raise case_permissions.case_not_found()
    return case


async def _load_calculation_inputs(db: AsyncSession, case, payload: CalculationInput):
    """Validasi bersama Hitung dan Simpan. Gagal di sini = tidak ada yang disimpan."""
    if case.pole_kind != PoleKind.standard:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only standard poles can be calculated yet",
        )
    height = await CalculationCaseRepository.get_height_for_calculation(db, payload.pole_standard_height_id)
    if height is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="poleStandardHeightId does not reference an existing pole standard height",
        )
    if height.pole_standard.type != PoleStandardType.taper:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only taper standard poles can be calculated yet",
        )
    
    arm_material_ids = {arm.material_id for arm in payload.arms}
    known_materials = await CalculationCaseRepository.material_names(db, arm_material_ids)
    if arm_material_ids - known_materials.keys():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="arms materialId does not reference an existing material",
        )

    ground_position = builder.resolve_ground_position(height, payload.ground_position)
    if ground_position is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"groundPosition {payload.ground_position.value} is not available for this pole standard height",
        )

    conditions = await RequestRepository.get_conditions(db, WorkType.calculation, case.request_id)
    design_standard = await CalculationCaseRepository.get_design_standard(db, conditions.design_standard_id)
    return height, ground_position, conditions, design_standard


def _run_read(run) -> CalculationRunRead:
    """Run beserta tampilan hasilnya, disusun saat dibaca."""
    read = CalculationRunRead.model_validate(run)
    if run.result_snapshot is not None:
        read.display = display.format_display(run.result_snapshot)
    return read


async def _load_run(db: AsyncSession, case, run_id: str):
    run = await CalculationCaseRepository.get_run(db, case.id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation run not found")
    return run



# ===== Hitung (G14): tanpa menulis apa pun =====
@routerCalculationRun.post("/{request_id}/calculation-cases/{case_id}/calculate")
async def calculate_case(
    request_id: str,
    case_id: str,
    payload: CalculationInput,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor)
    # Ground position dan panjang tanam divalidasi tetapi tidak dipakai: tidak dikirim ke engine.
    height, _, conditions, design_standard = await _load_calculation_inputs(db, case, payload)

    reason = builder.run_skip_reason(conditions, design_standard, height)
    if reason is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": reason.value, "message": builder.RUN_SKIP_MESSAGES[reason]},
        )

    # Belum ada salinan untuk Hitung: geometri dibaca dari katalog saat itu juga.
    engine_request = builder.build_pole_request(
        design_standard_code=design_standard.code,
        wind_speed=conditions.wind_speed,
        air_density=conditions.air_density,
        step_poles=height.step_poles,
        material_names=await CalculationCaseRepository.material_names(
            db, [s.material_id for s in height.step_poles] + [a.material_id for a in payload.arms],
        ),
        direct_objects=payload.direct_objects,
        overhead_wires=payload.overhead_wires,
        arms=payload.arms,
        evaluated_positions_m=height.evaluated_positions_m,
    )

    try:
        response = await post_engine(POLE_CALCULATE_PATH, engine_request)
        if response.status_code == 422:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "engine_rejected", "engineResponse": response.body},
            )
        run_status, _ = builder.read_summary(response.body)
        result_display = display.format_display(response.body)
    except (EngineUnavailable, KeyError, TypeError, ValueError) as e:
        logger.error(f"Calculate failed for case {case.id}: {e!r}")
        reason = builder.RunSkipReason.engine_unavailable
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": reason.value, "message": builder.RUN_SKIP_MESSAGES[reason]},
        )

    return success_response(
        data=CalculateResult(status=run_status, display=result_display),
        message="Calculation completed",
    )



# ===== Simpan (G15): input tersimpan, lalu run baru =====
@routerCalculationRun.post("/{request_id}/calculation-cases/{case_id}/runs")
async def save_and_run(
    request_id: str,
    case_id: str,
    payload: CalculationInput,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor, for_update=True)
    case_permissions.ensure_owner(actor, case)
    height, ground_position, conditions, design_standard = await _load_calculation_inputs(db, case, payload)

    # Transaksi 1: input. Tetap tersimpan apa pun hasil perhitungannya (AG17).
    await CalculationCaseRepository.save_input(db, case, height, payload, ground_position)
    detail = await case_detail(db, case.id)

    def not_created(reason: builder.RunSkipReason):
        return success_response(
            data=CalculationSaveResult(
                case=detail,
                run_not_created=RunNotCreated(reason=reason.value, message=builder.RUN_SKIP_MESSAGES[reason]),
            ),
            message="Calculation input saved; no run was created",
        )

    reason = builder.run_skip_reason(conditions, design_standard, height)
    if reason is not None:
        return not_created(reason)

    # Payload disusun ulang dari data yang baru disimpan, bukan dari body.
    engine_request = builder.build_pole_request(
        design_standard_code=design_standard.code,
        wind_speed=conditions.wind_speed,
        air_density=conditions.air_density,
        step_poles=detail.step_poles,
        material_names=await CalculationCaseRepository.material_names(
            db, [s.material_id for s in detail.step_poles] + [a.material_id for a in detail.arms],
        ),
        direct_objects=detail.direct_objects,
        overhead_wires=detail.overhead_wires,
        arms=detail.arms,
        evaluated_positions_m=detail.evaluated_positions_m,
    )

    input_snapshot = {
        "engine_request": engine_request,
        "context": builder.build_context(
            conditions=conditions, design_standard=design_standard, height=height,
            ground_position=ground_position, embedment_length_mm=payload.embedment_length_mm,
        ),
    }

    try:
        response = await post_engine(POLE_CALCULATE_PATH, engine_request)
        if response.status_code == 422:
            run_status, utilization_ratio, result_snapshot = StatusCalculationRun.failed, None, None
            error_snapshot = {"status_code": 422, "body": response.body}
        else:
            run_status, utilization_ratio = builder.read_summary(response.body)
            result_snapshot, error_snapshot = response.body, None
    except (EngineUnavailable, KeyError, TypeError, ValueError) as e:
        logger.error(f"Run not created for case {case.id}: {e!r}")
        return not_created(builder.RunSkipReason.engine_unavailable)

    # Transaksi 2: run immutable.
    run = await CalculationCaseRepository.create_run(
        db, case_id=case.id, run_by_user_id=actor.id, status=run_status,
        utilization_ratio=utilization_ratio, input_snapshot=input_snapshot,
        result_snapshot=result_snapshot, error_snapshot=error_snapshot,
    )

    return success_response(
        data=CalculationSaveResult(case=detail, run=_run_read(run)),
        status_code=status.HTTP_201_CREATED,
        message="Calculation input saved and run created",
    )



# ===== Riwayat run =====
@routerCalculationRun.get("/{request_id}/calculation-cases/{case_id}/runs")
async def list_runs(
    request_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor)
    rows = await CalculationCaseRepository.list_runs(db, case.id)
    return success_response(
        data=[CalculationRunSummary.model_validate(r) for r in rows],
        message="Calculation runs retrieved",
    )


@routerCalculationRun.get("/{request_id}/calculation-cases/{case_id}/runs/{run_id}")
async def get_run(
    request_id: str,
    case_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor)
    run = await _load_run(db, case, run_id)
    return success_response(
        data=_run_read(run),
        message="Calculation run retrieved",
    )



# ===== Data laporan =====
async def _report_response(db: AsyncSession, case, run):
    """Data laporan satu run beserta header case saat dibaca."""
    if run.status == StatusCalculationRun.failed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "run_failed", "message": "A failed run has no report"},
        )
    try:
        data = report.format_report(run)
    except report.ReportTemplateUnavailable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "report_template_unavailable",
                "message": "The design standard of this run has no report template yet",
            },
        )
    header = await ReportHeaderRepository.get(db, case.id)
    data.header = ReportHeaderRead.model_validate(header) if header is not None else None
    return success_response(data=data, message="Calculation report retrieved")


# Laporan case: selalu dari run terbaru, dan hanya bila run itu masih menggambarkan isian
# dan kondisi yang tersimpan. Tidak mundur ke run lama.
@routerCalculationRun.get("/{request_id}/calculation-cases/{case_id}/report")
async def get_case_report(
    request_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor)
    run = await CalculationCaseRepository.latest_run(db, case.id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "no_run", "message": "The case has no calculation run yet"},
        )
    conditions = await RequestRepository.get_conditions(db, WorkType.calculation, case.request_id)
    causes = builder.run_stale_causes(case, run, conditions)
    if causes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "run_stale",
                "message": "The latest run no longer matches the saved input; save the calculation again",
                "causes": causes,
                "runId": run.id,
            },
        )
    return await _report_response(db, case, run)


# Riwayat: laporan run tertentu, tanpa pemeriksaan basi.
@routerCalculationRun.get("/{request_id}/calculation-cases/{case_id}/runs/{run_id}/report")
async def get_run_report(
    request_id: str,
    case_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor)
    run = await _load_run(db, case, run_id)
    return await _report_response(db, case, run)
