from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake import permissions as intake_permissions
from app.modules.intake.repository import RequestRepository
from app.modules.workflow.repository import RequestEventRepository
from app.modules.case import permissions as case_permissions
from app.modules.case.repository import CaseRepository
from app.modules.files.repository import FileRepository
from app.modules.files import storage
from app.modules.drawing.repository import DrawingCaseRepository
from app.modules.drawing.schemas import DrawingCaseCreate, DrawingCaseRead, DrawingCaseUpdate
from app.database.models.workflow import WorkType

routerDrawingCase = APIRouter(prefix="/api/requests", tags=["Drawing"])

# Baca: pihak Koribali. Tulis: pengerja; superadmin tidak pernah menjadi owner case.
_READ_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")
_WORKER_ROLE = require_roles("admin_department", "drafter_checker", "drafter")



# ===== Helper =====
def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


async def _load_case(db: AsyncSession, request_id: str, case_id: str, actor: CurrentUser):
    await case_permissions.load_readable_request(db, request_id, actor)
    case = await DrawingCaseRepository.get_in_request(db, request_id, case_id)
    if case is None:
        raise case_permissions.case_not_found()
    return case


async def _ensure_calculation_ref(db: AsyncSession, request_id: str, data: dict) -> None:
    calculation_case_id = data.get("calculation_case_id")
    if calculation_case_id is not None and not await DrawingCaseRepository.calculation_case_in_request(
        db, request_id, calculation_case_id,
    ):
        raise _unprocessable("calculationCaseId does not reference a calculation case of this request")



# ===== Read =====
@routerDrawingCase.get("/{request_id}/drawing-cases")
async def list_drawing_cases(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    await case_permissions.load_readable_request(db, request_id, actor)
    rows = await DrawingCaseRepository.list_by_request(db, request_id)
    return success_response(
        data=[DrawingCaseRead.model_validate(c) for c in rows],
        message="Drawing cases retrieved",
    )


@routerDrawingCase.get("/{request_id}/drawing-cases/{case_id}")
async def get_drawing_case(
    request_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor)
    return success_response(data=DrawingCaseRead.model_validate(case), message="Drawing case retrieved")



# ===== Create (pengerja drawing yang aktif) =====
@routerDrawingCase.post("/{request_id}/drawing-cases")
async def create_drawing_case(
    request_id: str,
    payload: DrawingCaseCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    # Kunci request: case baru ikut menentukan status prevention_check.
    req = await case_permissions.load_readable_request(db, request_id, actor, for_update=True)
    await case_permissions.ensure_can_create(db, actor, req, WorkType.drawing)
    conditions = await RequestRepository.get_conditions(db, WorkType.drawing, req.id)
    if conditions is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Drawing conditions must be defined before creating a drawing case",
        )

    data = payload.model_dump(exclude_unset=True)
    # Isian awal satu arah, hanya saat create: judul dari subject (G5),
    # tipe drawing dari drawing conditions (G8), bukan dari referensi sharedDetails.
    data["title"] = payload.title or req.subject
    if not data["title"]:
        raise _unprocessable("title is required because the request has no subject")
    if payload.drawing_type is None:
        data["drawing_type"] = conditions.drawing_type
    await _ensure_calculation_ref(db, req.id, data)

    case = await DrawingCaseRepository.create(db, req, owner_user_id=actor.id, data=data)
    return success_response(
        data=DrawingCaseRead.model_validate(case),
        status_code=status.HTTP_201_CREATED,
        message="Drawing case created",
    )



# ===== Update (owner saja) =====
@routerDrawingCase.patch("/{request_id}/drawing-cases/{case_id}")
async def update_drawing_case(
    request_id: str,
    case_id: str,
    payload: DrawingCaseUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    case = await _load_case(db, request_id, case_id, actor)
    case_permissions.ensure_owner(actor, case)
    data = payload.model_dump(exclude_unset=True)
    await _ensure_calculation_ref(db, request_id, data)
    case = await DrawingCaseRepository.update(db, case, data)
    return success_response(data=DrawingCaseRead.model_validate(case), message="Drawing case saved")



# ===== Delete (owner atau admin_department, sebelum pernah diperiksa) =====
@routerDrawingCase.delete("/{request_id}/drawing-cases/{case_id}")
async def delete_drawing_case(
    request_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    # Kunci request: check yang datang bersamaan menunggu sampai hapus selesai.
    req = await RequestEventRepository.get_for_update(db, request_id)
    if req is None or not await intake_permissions.is_readable(db, actor, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    case = await DrawingCaseRepository.get_in_request(db, request_id, case_id)
    if case is None:
        raise case_permissions.case_not_found()
    case_permissions.ensure_owner_or_admin(actor, case, "delete it")
    if await CaseRepository.has_check(db, WorkType.drawing, case.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A case that has been checked cannot be deleted",
        )
    # Deliverable case ikut terhapus (CASCADE), objek storage-nya dibersihkan sesudah commit.
    storage_refs = await FileRepository.storage_refs_for_case(db, WorkType.drawing, case.id)
    await DrawingCaseRepository.delete(db, req, case)
    await storage.discard(storage_refs)
    return success_response(data={"deleted": True}, message="Drawing case deleted")
