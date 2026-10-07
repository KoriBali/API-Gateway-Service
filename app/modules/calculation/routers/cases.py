from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake.repository import RequestRepository
from app.modules.intake import permissions
from app.modules.calculation.repository import CalculationCaseRepository
from app.modules.calculation.schemas import (
    CalculationCaseUpsert,
    CalculationCaseRead,
)

routerCalculationCase = APIRouter(prefix="/api/requests", tags=["Calculation"])

_ANY_ROLE = require_roles("superadmin", "admin", "drafter")


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

    case = await CalculationCaseRepository.upsert(
        db, request_id=request_id, owner_user_id=actor.id, payload=payload
    )
    return success_response(
        data=CalculationCaseRead.model_validate(case),
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
    if req is None or not permissions.can_read_request(actor, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    case = await CalculationCaseRepository.get_by_request(db, request_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation case not found for this request",
        )
    return success_response(
        data=CalculationCaseRead.model_validate(case),
        message="Calculation case retrieved",
    )