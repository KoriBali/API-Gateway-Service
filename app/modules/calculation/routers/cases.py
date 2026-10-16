from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake import permissions as intake_permissions
from app.modules.workflow.repository import RequestEventRepository
from app.modules.case import permissions as case_permissions
from app.modules.case.repository import CaseRepository
from app.modules.files.repository import FileRepository
from app.modules.files import storage
from app.modules.calculation.repository import CalculationCaseRepository
from app.modules.calculation.schemas import (
    CalculationCaseCreate,
    CalculationCaseRead,
    CalculationCaseUpdate,
)
from app.database.models.workflow import WorkType

routerCalculationCase = APIRouter(prefix="/api/requests", tags=["Calculation"])

# Baca: pihak Koribali. Tulis: pengerja; superadmin tidak pernah menjadi owner case.
_READ_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")
_WORKER_ROLE = require_roles("admin_department", "drafter_checker", "drafter")



# ===== Helper =====
async def _load_case(db: AsyncSession, request_id: str, case_id: str, actor: CurrentUser):
    await case_permissions.load_readable_request(db, request_id, actor)
    case = await CalculationCaseRepository.get_in_request(db, request_id, case_id)
    if case is None:
        raise case_permissions.case_not_found()
    return case



# ===== Read =====
@routerCalculationCase.get("/{request_id}/calculation-cases")
async def list_calculation_cases(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    await case_permissions.load_readable_request(db, request_id, actor)
    rows = await CalculationCaseRepository.list_by_request(db, request_id)
    return success_response(
        data=[CalculationCaseRead.model_validate(c) for c in rows],
        message="Calculation cases retrieved",
    )


@routerCalculationCase.get("/{request_id}/calculation-cases/{case_id}")
async def get_calculation_case(
    request_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor)
    return success_response(
        data=CalculationCaseRead.model_validate(case),
        message="Calculation case retrieved",
    )



# ===== Create (pengerja calculation yang aktif) =====
@routerCalculationCase.post("/{request_id}/calculation-cases")
async def create_calculation_case(
    request_id: str,
    payload: CalculationCaseCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    # Kunci request: case baru ikut menentukan status prevention_check.
    req = await case_permissions.load_readable_request(db, request_id, actor, for_update=True)
    await case_permissions.ensure_can_create(db, actor, req, WorkType.calculation)

    data = payload.model_dump(exclude_unset=True)
    # Isian awal judul dari requests.subject. Satu arah, hanya saat create.
    data["title"] = payload.title or req.subject
    if not data["title"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="title is required because the request has no subject",
        )

    case = await CalculationCaseRepository.create(
        db, req, owner_user_id=actor.id, data=data,
    )
    return success_response(
        data=CalculationCaseRead.model_validate(case),
        status_code=status.HTTP_201_CREATED,
        message="Calculation case created",
    )



# ===== Update (owner saja) =====
@routerCalculationCase.patch("/{request_id}/calculation-cases/{case_id}")
async def update_calculation_case(
    request_id: str,
    case_id: str,
    payload: CalculationCaseUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor)
    case_permissions.ensure_owner(actor, case)
    case = await CalculationCaseRepository.update(db, case, payload.model_dump(exclude_unset=True))
    return success_response(
        data=CalculationCaseRead.model_validate(case),
        message="Calculation case saved",
    )



# ===== Delete (owner atau admin_department, sebelum pernah diperiksa) =====
@routerCalculationCase.delete("/{request_id}/calculation-cases/{case_id}")
async def delete_calculation_case(
    request_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    # Kunci request: check yang datang bersamaan menunggu sampai hapus selesai.
    req = await RequestEventRepository.get_for_update(db, request_id)
    if req is None or not await intake_permissions.is_readable(db, actor, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    case = await CalculationCaseRepository.get_in_request(db, request_id, case_id)
    if case is None:
        raise case_permissions.case_not_found()
    case_permissions.ensure_owner_or_admin(actor, case, "delete it")
    if await CaseRepository.has_check(db, WorkType.calculation, case.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A case that has been checked cannot be deleted",
        )
    # Deliverable case ikut terhapus (CASCADE), objek storage-nya dibersihkan sesudah commit.
    storage_refs = await FileRepository.storage_refs_for_case(db, WorkType.calculation, case.id)
    await CalculationCaseRepository.delete(db, req, case)
    await storage.discard(storage_refs)
    return success_response(data={"deleted": True}, message="Calculation case deleted")