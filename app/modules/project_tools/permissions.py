from fastapi import HTTPException, status

from app.core.security import CurrentUser
from app.database.models.calculation import CalculationCondition
from app.database.models.intake import Request
from app.database.models.workflow import WorkType
from app.modules.assignment.permissions import WORK_TYPES_OF
from app.modules.case.permissions import ensure_request_open
from app.modules.project_tools.schemas import PoleToolConditions


def ensure_can_save_to(actor: CurrentUser, request: Request, work_type: WorkType) -> None:
    """Request yang sudah ada boleh menerima Simpan: satu department dengan user, masih
    terbuka (internal / prevention_check), dan designType mencakup work type tool.
    Ditulis per work type supaya drawing tool kelak memakainya."""
    if actor.department_id is None or request.responsible_department_id != actor.department_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The request belongs to another department",
        )
    ensure_request_open(request)
    if work_type not in WORK_TYPES_OF[request.design_type]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "work_type_not_in_design_type",
                "designType": request.design_type.value,
                "message": f"workType '{work_type.value}' is not part of the request designType "
                           f"'{request.design_type.value}'",
            },
        )


def _calculation_conditions_read(row: CalculationCondition) -> dict:
    return {
        "designStandardId": row.design_standard_id,
        "windSpeed": float(row.wind_speed) if row.wind_speed is not None else None,
        "airDensity": float(row.air_density),
        "horizontalAcceleration": float(row.horizontal_acceleration) if row.horizontal_acceleration is not None else None,
        "responseRatio": float(row.response_ratio) if row.response_ratio is not None else None,
    }


def ensure_calculation_conditions_match(existing: CalculationCondition | None, tool: PoleToolConditions) -> None:
    """Conditions request yang sudah ada harus sama dengan conditions sesi tool. Tidak ada
    opsi timpa: mengubah conditions request tetap lewat endpoint conditions."""
    if existing is None:
        return
    current = _calculation_conditions_read(existing)
    sent = {
        "designStandardId": tool.design_standard_id,
        "windSpeed": tool.wind_speed,
        "airDensity": tool.air_density,
        "horizontalAcceleration": tool.horizontal_acceleration,
        "responseRatio": tool.response_ratio,
    }
    different = [field for field in sent if current[field] != sent[field]]
    if different:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "conditions_mismatch",
                "message": "The request already has different calculation conditions",
                "requestConditions": current,
                "toolConditions": sent,
                "differentFields": different,
            },
        )
