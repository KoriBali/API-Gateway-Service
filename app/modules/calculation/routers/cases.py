from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.identity.repository import RequestRepository
from app.modules.identity import permissions
from app.database.models.identity import RequestStatus
from app.modules.calculation.repository import CalculationCaseRepository
from app.modules.calculation.schemas import (
    CalculationCaseUpsert,
    CalculationCaseRead,
    ConditionInput,
)

routerCalculationCase = APIRouter(prefix="/api/requests", tags=["Calculation"])

_ANY_ROLE = require_roles("superadmin", "admin", "drafter")


def _to_read(case) -> CalculationCaseRead:
    """Bangun response, termasuk condition (0..1) dari relasi."""
    cond = None
    conditions = getattr(case, "conditions", None) or []
    if conditions:
        c = conditions[0]
        cond = ConditionInput(
            design_standard_id=c.design_standard_id,
            wind_speed=c.wind_speed,
            air_density=c.air_density,
        )
    read = CalculationCaseRead.model_validate(case)
    read.condition = cond
    return read


# ===== Save Draft =====
@routerCalculationCase.put("/{request_id}/calculation-case")
async def save_calculation_case(
    request_id: str,
    payload: CalculationCaseUpsert,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await RequestRepository.get_by_id(db, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    permissions.ensure_can_manage_request(actor, req)

    if req.status != RequestStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft requests can be edited",
        )

    case = await CalculationCaseRepository.upsert(
        db, request_id=request_id, owner_user_id=actor.id, payload=payload
    )
    # Reload dgn condition utk response konsisten dgn GET.
    case = await CalculationCaseRepository.get_with_children(db, request_id)
    return success_response(
        data=_to_read(case),
        message="Calculation draft saved",
    )


# ===== Resume draft =====
@routerCalculationCase.get("/{request_id}/calculation-case")
async def get_calculation_case(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await RequestRepository.get_by_id(db, request_id)
    if req is None or not _can_read(actor, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    case = await CalculationCaseRepository.get_with_children(db, request_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation case not found for this request",
        )
    return success_response(data=_to_read(case), message="Calculation case retrieved")


def _can_read(actor: CurrentUser, req) -> bool:
    if actor.role == "superadmin":
        return True
    if actor.role == "admin":
        return actor.department_id is not None and \
            req.responsible_department_id == actor.department_id
    return req.created_by_user_id == actor.id