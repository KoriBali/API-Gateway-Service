from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake.repository import RequestRepository
from app.modules.case import permissions as case_permissions
from app.modules.calculation import builder, display, report
from app.modules.calculation.repository import CalculationCaseRepository
from app.modules.calculation.routers.cases import case_detail
from app.modules.calculation.schemas import (
    CalculateResult,
    CalculationInput,
    CalculationRunRead,
    CalculationRunSummary,
    CalculationSaveResult,
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
    expected = builder.CATALOG_GROUND_POSITION.get(payload.ground_position)
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"groundPosition {payload.ground_position.value} has no catalog pole height",
        )
    if height.ground_position != expected:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"groundPosition {payload.ground_position.value} requires a "
                f"{expected.value} pole height"
            ),
        )
    conditions = await RequestRepository.get_conditions(db, WorkType.calculation, case.request_id)
    design_standard = await CalculationCaseRepository.get_design_standard(db, conditions.design_standard_id)
    return height, conditions, design_standard


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
    height, conditions, design_standard = await _load_calculation_inputs(db, case, payload)

    reason = builder.run_skip_reason(conditions, design_standard, height)
    if reason is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": reason.value, "message": builder.RUN_SKIP_MESSAGES[reason]},
        )

    # Belum ada salinan untuk Hitung: geometri dibaca dari katalog saat itu juga.
    engine_request = builder.build_pole_request(
        design_standard_code=design_standard.code,
        segments=height.segments,
        material_names={s.material_id: s.material.name for s in height.segments},
        direct_objects=payload.direct_objects,
        evaluated_positions_m=height.evaluated_positions_m,
        overdesign_factor=payload.overdesign_factor,
    )
    try:
        response = await post_engine(POLE_CALCULATE_PATH, engine_request)
        if response.status_code == 422:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason": "engine_rejected", "engineResponse": response.body},
            )
        run_status = builder.derive_status(response.body)
        result_display = display.format_display(response.body)
    except (EngineUnavailable, KeyError, TypeError, ValueError) as e:
        logger.error(f"Calculate failed for case {case.id}: {e!r}")
        reason = builder.RunSkipReason.engine_unavailable
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": reason.value, "message": builder.RUN_SKIP_MESSAGES[reason]},
        )

    return success_response(
        data=CalculateResult(
            status=run_status, display=result_display,
            engine_request=engine_request, engine_result=response.body,
        ),
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
    height, conditions, design_standard = await _load_calculation_inputs(db, case, payload)

    # Transaksi 1: input. Tetap tersimpan apa pun hasil perhitungannya (AG17).
    await CalculationCaseRepository.save_input(db, case, height, payload)
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
        segments=detail.step_poles,
        material_names=await CalculationCaseRepository.material_names(db, [s.material_id for s in detail.step_poles]),
        direct_objects=detail.direct_objects,
        evaluated_positions_m=detail.evaluated_positions_m,
        overdesign_factor=detail.overdesign_factor,
    )
    input_snapshot = {
        "engine_request": engine_request,
        "context": builder.build_context(
            conditions=conditions, design_standard=design_standard,
            height=height, ground_position=payload.ground_position,
        ),
    }

    try:
        response = await post_engine(POLE_CALCULATE_PATH, engine_request)
        if response.status_code == 422:
            run_status, result_snapshot = StatusCalculationRun.failed, None
            error_snapshot = {"status_code": 422, "body": response.body}
        else:
            run_status, result_snapshot, error_snapshot = builder.derive_status(response.body), response.body, None
    except (EngineUnavailable, KeyError, TypeError, ValueError) as e:
        logger.error(f"Run not created for case {case.id}: {e!r}")
        return not_created(builder.RunSkipReason.engine_unavailable)

    # Transaksi 2: run immutable.
    run = await CalculationCaseRepository.create_run(
        db, case_id=case.id, run_by_user_id=actor.id, status=run_status,
        input_snapshot=input_snapshot, result_snapshot=result_snapshot, error_snapshot=error_snapshot,
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
    return success_response(data=data, message="Calculation report retrieved")