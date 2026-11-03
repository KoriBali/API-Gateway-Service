import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.case import permissions as case_permissions
from app.modules.calculation.repository import CalculationCaseRepository
from app.modules.calculation.schemas import (
    CALCULATION_DRAFT_KEYS,
    CALCULATION_DRAFT_MAX_BYTES,
    CalculationDraftRead,
)

routerCalculationDraft = APIRouter(prefix="/api/requests", tags=["Calculation"])

# Draft milik owner case, sama dengan Simpan. Peran lain tidak membaca draft.
_WORKER_ROLE = require_roles("admin_department", "drafter_checker", "drafter")



# ===== Helper =====
async def _load_own_case(db: AsyncSession, request_id: str, case_id: str, actor: CurrentUser):
    await case_permissions.load_readable_request(db, request_id, actor)
    case = await CalculationCaseRepository.get_in_request(db, request_id, case_id)
    if case is None:
        raise case_permissions.case_not_found()
    case_permissions.ensure_owner(actor, case)
    return case


def _draft_read(case) -> CalculationDraftRead | None:
    if case.input_draft is None:
        return None
    return CalculationDraftRead(input=case.input_draft, saved_at=case.input_draft_saved_at)



# ===== Baca =====
@routerCalculationDraft.get("/{request_id}/calculation-cases/{case_id}/calculation-draft")
async def get_calculation_draft(
    request_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    case = await _load_own_case(db, request_id, case_id, actor)
    return success_response(data=_draft_read(case), message="Calculation draft retrieved")



# ===== Simpan draft (tanpa run) =====
@routerCalculationDraft.put("/{request_id}/calculation-cases/{case_id}/calculation-draft")
async def put_calculation_draft(
    request_id: str,
    case_id: str,
    payload: dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    case = await _load_own_case(db, request_id, case_id, actor)
    unknown = sorted(payload.keys() - CALCULATION_DRAFT_KEYS)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown calculation draft keys: {', '.join(unknown)}",
        )
    if len(json.dumps(payload).encode()) > CALCULATION_DRAFT_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Calculation draft exceeds {CALCULATION_DRAFT_MAX_BYTES} bytes",
        )
    await CalculationCaseRepository.put_draft(db, case, payload)
    return success_response(data=_draft_read(case), message="Calculation draft saved")



# ===== Buang draft =====
@routerCalculationDraft.delete("/{request_id}/calculation-cases/{case_id}/calculation-draft")
async def delete_calculation_draft(
    request_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    case = await _load_own_case(db, request_id, case_id, actor)
    await CalculationCaseRepository.delete_draft(db, case)
    return success_response(data=None, message="Calculation draft discarded")
