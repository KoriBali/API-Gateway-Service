from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake import permissions
from app.modules.intake.request_no import RequestNoWarning, parse_request_no, tail_matches_brand
from app.modules.intake.repository import ProjectRepository, RequestRepository
from app.database.models.intake import (
    BrandLine,
    RequestStatus,
    RequestType,
    DesignType,
    RequestClassification,
)
from app.modules.intake.schemas import (
    DRAWING_DESIGN_TYPES,
    RequestCreate,
    RequestUpdate,
    RequestRead,
    RequestDetailRead,
    SharedDetailsWrite,
    YpDetailsWrite,
    YsDetailsWrite,
    FinishWrite,
    ConditionsUpdate,
    RequestNoCheckRead,
    RequestNoDuplicate,
)

routerRequest = APIRouter(prefix="/api/requests", tags=["Requests"])

# Semua role terautentikasi boleh menyentuh modul ini, scope sudah di setting
_ANY_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")



# ===== Helper =====
def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


async def _ensure_project_matches(db: AsyncSession, project_id: str, brand_line: BrandLine) -> None:
    """Project wajib ada dan berform sama dengan request (juga dijaga FK komposit di DB)."""
    project = await ProjectRepository.get_by_id(db, project_id)
    if project is None:
        raise _unprocessable("projectId does not reference an existing project")
    if project.request_form != brand_line:
        raise _unprocessable("projectId references a project with a different request form")


async def _ensure_region_exists(db: AsyncSession, region_id: str | None) -> None:
    if region_id is not None and not await RequestRepository.region_exists(db, region_id):
        raise _unprocessable("sharedDetails.regionId does not reference an existing region")


async def _ensure_material_exists(db: AsyncSession, material_id: str | None) -> None:
    if material_id is not None and not await RequestRepository.material_exists(db, material_id):
        raise _unprocessable("ysDetails.materialId does not reference an existing material")


def _ensure_drawing_fields(design_type, region_id, drawing_type) -> None:
    """DD invariant intake 11, diperiksa pada keadaan SESUDAH perubahan."""
    if design_type in DRAWING_DESIGN_TYPES and (region_id is None or drawing_type is None):
        raise _unprocessable(
            "sharedDetails.regionId and sharedDetails.drawingType are required "
            "when designType includes drawing"
        )


async def _load_managed(db: AsyncSession, request_id: str, actor: CurrentUser):
    """Ambil request untuk diubah: 404 bila tidak ada, 403 bila tidak berhak."""
    req = await RequestRepository.get_by_id(db, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    permissions.ensure_can_manage_request(actor, req)
    return req


async def _detail_response(db: AsyncSession, request_id: str, message: str, status_code: int = 200):
    req = await RequestRepository.get_detail(db, request_id)
    return success_response(
        data=RequestDetailRead.model_validate(req),
        status_code=status_code,
        message=message,
    )



# ===== Read (semua role, discope) =====
@routerRequest.get("")
async def list_requests(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
    brand_line: BrandLine | None = Query(default=None, alias="brandLine"),
    project_id: str | None = Query(default=None, alias="projectId"),
    request_type: RequestType | None = Query(default=None, alias="requestType"),
    request_classification: RequestClassification | None = Query(default=None, alias="requestClassification"),
    design_type: DesignType | None = Query(default=None, alias="designType"),
    pole_category_id: str | None = Query(default=None, alias="poleCategoryId"),
    due_from: date | None = Query(default=None, alias="dueFrom"),
    due_to: date | None = Query(default=None, alias="dueTo"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
):
    rows, total = await RequestRepository.list_scoped(
        db,
        role=actor.role,
        actor_id=actor.id,
        actor_department_id=actor.department_id,
        brand_line=brand_line,
        project_id=project_id,
        request_type=request_type,
        request_classification=request_classification,
        design_type=design_type,
        pole_category_id=pole_category_id,
        due_from=due_from,
        due_to=due_to,
        limit=limit,
        offset=offset,
        status=status_filter,
    )
    items = [RequestRead.model_validate(r) for r in rows]
    return success_response(
        data={"items": items, "total": total, "limit": limit, "offset": offset},
        message="Requests retrieved",
    )


# Path statis WAJIB didaftarkan sebelum "/{request_id}", kalau tidak tertelan sebagai request_id.
@routerRequest.get("/request-no-check")
async def check_request_no(
    request_no: str = Query(alias="requestNo", min_length=1, max_length=100),
    brand_mark: BrandLine | None = Query(default=None, alias="brandMark"),
    exclude_request_id: str | None = Query(default=None, alias="excludeRequestId"),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    """Usulan segmen 図番 + peringatan intake YP. Tidak pernah menolak dan tidak menulis apa pun.

    Dipanggil form intake YP saja (DD invariant intake 9). Pencarian kembar tetap
    memeriksa seluruh requests.request_no, karena kolom itu milik kedua form.
    """
    warnings: list[str] = []
    project_id = None

    segments = parse_request_no(request_no)
    if segments is None:
        warnings.append(RequestNoWarning.PATTERN_MISMATCH)
    else:
        if not tail_matches_brand(segments.tail_code, brand_mark):
            warnings.append(RequestNoWarning.TAIL_BRAND_MISMATCH)
        # Identitas project = head + base (tanpa tail). Bantu frontend memilih project yang sudah ada.
        project = await ProjectRepository.find_by_identity(
            db, request_form=BrandLine.yp, scope_code=segments.scope_code, pj_no=segments.pj_no,
        )
        project_id = project.id if project is not None else None

    others = await RequestRepository.list_by_request_no(
        db, request_no, exclude_request_id=exclude_request_id,
    )
    if others:
        warnings.append(RequestNoWarning.DUPLICATE)
    # Jumlah dihitung dari semua request; rinciannya hanya yang boleh dibaca actor.
    visible = [r for r in others if permissions.can_read_request(actor, r)]

    return success_response(
        data=RequestNoCheckRead(
            request_no=request_no,
            matches_pattern=segments is not None,
            segments=segments,
            project_id=project_id,
            warnings=warnings,
            duplicate_count=len(others),
            duplicates=[RequestNoDuplicate.model_validate(r) for r in visible],
        ),
        message="Request number checked",
    )


@routerRequest.get("/{request_id}")
async def get_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await RequestRepository.get_detail(db, request_id)
    if req is None or not permissions.can_read_request(actor, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return success_response(
        data=RequestDetailRead.model_validate(req),
        message="Request retrieved",
    )



# ===== Create / intake (semua role, self-assign) =====
@routerRequest.post("")
async def create_request(
    payload: RequestCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    # responsible_department_id dikunci ke departemen pembuat
    if actor.department_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no department; cannot create a request",
        )

    if payload.project_id is not None:
        await _ensure_project_matches(db, payload.project_id, payload.brand_line)
    if not await RequestRepository.pole_category_exists(db, payload.pole_category_id):
        raise _unprocessable("poleCategoryId does not reference an existing pole category")
    if payload.shared_details is not None:
        await _ensure_region_exists(db, payload.shared_details.region_id)
    if payload.ys_details is not None:
        await _ensure_material_exists(db, payload.ys_details.material_id)
    if not await RequestRepository.design_standard_exists(db, payload.conditions.design_standard_id):
        raise _unprocessable("conditions.designStandardId does not reference an existing design standard")

    req = await RequestRepository.create(
        db,
        payload,
        created_by_user_id=actor.id,
        responsible_department_id=actor.department_id,
    )
    return await _detail_response(db, req.id, "Request created", status.HTTP_201_CREATED)



# ===== Update kolom request (pembuat / admin-dept / superadmin) =====
@routerRequest.patch("/{request_id}")
async def update_request(
    request_id: str,
    payload: RequestUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await _load_managed(db, request_id, actor)

    data = payload.model_dump(exclude_unset=True)
    if data.get("project_id") is not None and data["project_id"] != req.project_id:
        await _ensure_project_matches(db, data["project_id"], req.brand_line)
    if "pole_category_id" in data and data["pole_category_id"] != req.pole_category_id:
        if not await RequestRepository.pole_category_exists(db, data["pole_category_id"]):
            raise _unprocessable("poleCategoryId does not reference an existing pole category")
    if "design_type" in data:
        shared = await RequestRepository.get_shared_details(db, req.id)
        _ensure_drawing_fields(
            data["design_type"],
            shared.region_id if shared is not None else None,
            shared.drawing_type if shared is not None else None,
        )

    await RequestRepository.update(db, req, payload)
    return await _detail_response(db, request_id, "Request updated")



# ===== Update tabel bersama, ekstensi form, finish, conditions =====
@routerRequest.patch("/{request_id}/shared-details")
async def update_shared_details(
    request_id: str,
    payload: SharedDetailsWrite,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await _load_managed(db, request_id, actor)
    data = payload.model_dump(exclude_unset=True)
    await _ensure_region_exists(db, data.get("region_id"))

    # Keadaan sesudah PATCH = nilai yang dikirim, atau nilai lama bila tidak dikirim.
    shared = await RequestRepository.get_shared_details(db, req.id)
    _ensure_drawing_fields(
        req.design_type,
        data.get("region_id", shared.region_id if shared is not None else None),
        data.get("drawing_type", shared.drawing_type if shared is not None else None),
    )

    await RequestRepository.update_shared_details(db, req, payload)
    return await _detail_response(db, request_id, "Shared details updated")


@routerRequest.patch("/{request_id}/yp-details")
async def update_yp_details(
    request_id: str,
    payload: YpDetailsWrite,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await _load_managed(db, request_id, actor)
    if req.brand_line != BrandLine.yp:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="ypDetails only apply to a YP request")
    await RequestRepository.update_yp_details(db, req, payload)
    return await _detail_response(db, request_id, "YP details updated")


@routerRequest.patch("/{request_id}/ys-details")
async def update_ys_details(
    request_id: str,
    payload: YsDetailsWrite,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await _load_managed(db, request_id, actor)
    if req.brand_line != BrandLine.ys:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="ysDetails only apply to a YS request")
    await _ensure_material_exists(db, payload.material_id)
    await RequestRepository.update_ys_details(db, req, payload)
    return await _detail_response(db, request_id, "YS details updated")


@routerRequest.patch("/{request_id}/finish")
async def update_finish(
    request_id: str,
    payload: FinishWrite,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await _load_managed(db, request_id, actor)
    await RequestRepository.update_finish(db, req, payload)
    return await _detail_response(db, request_id, "Finish updated")


@routerRequest.patch("/{request_id}/conditions")
async def update_conditions(
    request_id: str,
    payload: ConditionsUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await _load_managed(db, request_id, actor)
    cond = await RequestRepository.get_conditions(db, req.id)
    if cond is None:
        # Baris conditions lahir bersama request; tidak ada berarti data rusak.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Conditions not found for this request")
    data = payload.model_dump(exclude_unset=True)
    if "design_standard_id" in data and data["design_standard_id"] != cond.design_standard_id:
        if not await RequestRepository.design_standard_exists(db, data["design_standard_id"]):
            raise _unprocessable("designStandardId does not reference an existing design standard")
    await RequestRepository.update_conditions(db, cond, payload)
    return await _detail_response(db, request_id, "Conditions updated")



# ===== Delete (pembuat / admin-dept / superadmin) =====
@routerRequest.delete("/{request_id}")
async def delete_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await _load_managed(db, request_id, actor)

    # Request yang sudah menyeberang ke sisi Jepang tidak boleh hilang.
    if req.status != RequestStatus.internal:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Only internal requests can be deleted")

    await RequestRepository.delete(db, req)
    return success_response(data={"deleted": True}, message="Request deleted")