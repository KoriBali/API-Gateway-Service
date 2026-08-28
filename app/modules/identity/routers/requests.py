from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response, to_json
from app.modules.identity.repository import RequestRepository
from app.modules.identity import permissions
from app.database.models.identity import (
    RequestType,
    DesignType,
    RequestCategory,
)
from app.modules.identity.schemas import (
    RequestCreate,
    RequestUpdate,
    RequestRead,
)

routerRequest = APIRouter(prefix="/api/requests", tags=["Requests"])

# Semua role terautentikasi boleh menyentuh modul ini, scope sudah di setting
_ANY_ROLE = require_roles("superadmin", "admin", "drafter")



def _can_read(actor: CurrentUser, req) -> bool:
    if actor.role == "superadmin":
        return True
    if actor.role == "admin":
        return actor.department_id is not None and \
            req.responsible_department_id == actor.department_id
    return req.created_by_user_id == actor.id


# ===== Read (semua role, discope) =====
@routerRequest.get("")
async def list_requests(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
    request_type: RequestType | None = Query(default=None, alias="requestType"),
    request_category: RequestCategory | None = Query(default=None, alias="requestCategory"),
    design_type: DesignType | None = Query(default=None, alias="designType"),
    pole_category_id: str | None = Query(default=None, alias="poleCategoryId"),
    due_from: date | None = Query(default=None, alias="dueFrom"),
    due_to: date | None = Query(default=None, alias="dueTo"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    rows, total = await RequestRepository.list_scoped(
        db,
        role=actor.role,
        actor_id=actor.id,
        actor_department_id=actor.department_id,
        request_type=request_type,
        request_category=request_category,
        design_type=design_type,
        pole_category_id=pole_category_id,
        due_from=due_from,
        due_to=due_to,
        limit=limit,
        offset=offset,
    )
    items = [to_json(RequestRead.model_validate(r)) for r in rows]
    return success_response(
        data={"items": items, "total": total, "limit": limit, "offset": offset},
        to_camel=False,
        message="Requests retrieved",
    )


@routerRequest.get("/{request_id}")
async def get_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await RequestRepository.get_by_id(db, request_id)
    if req is None or not _can_read(actor, req):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return success_response(
        data=to_json(RequestRead.model_validate(req)),
        to_camel=False,
        message="Request retrieved",
    )


# ===== Create (semua role, self-assign) =====
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
    # Validasi FK pole_category_id
    if not await RequestRepository.pole_category_exists(db, payload.pole_category_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="poleCategoryId does not reference an existing pole category",
        )

    req = await RequestRepository.create(
        db,
        payload,
        created_by_user_id=actor.id,
        responsible_department_id=actor.department_id,
    )
    return success_response(
        data=to_json(RequestRead.model_validate(req)),
        to_camel=False,
        status_code=status.HTTP_201_CREATED,
        message="Request created",
    )


# ===== Update (pembuat / admin-dept / superadmin) =====
@routerRequest.patch("/{request_id}")
async def update_request(
    request_id: str,
    payload: RequestUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await RequestRepository.get_by_id(db, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    permissions.ensure_can_manage_request(actor, req)

    data = payload.model_dump(exclude_unset=True)
    if "pole_category_id" in data and data["pole_category_id"] != req.pole_category_id:
        if not await RequestRepository.pole_category_exists(db, data["pole_category_id"]):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="poleCategoryId does not reference an existing pole category",
            )

    updated = await RequestRepository.update(db, req, payload)
    return success_response(
        data=to_json(RequestRead.model_validate(updated)),
        to_camel=False,
        message="Request updated",
    )


# ===== Delete (guarded; pembuat / admin-dept / superadmin) =====
@routerRequest.delete("/{request_id}")
async def delete_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_ANY_ROLE),
):
    req = await RequestRepository.get_by_id(db, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    permissions.ensure_can_manage_request(actor, req)

    calc_count, draw_count = await RequestRepository.count_children(db, request_id)
    if calc_count > 0 or draw_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Request still has {calc_count} calculation case(s) and "
                f"{draw_count} drawing case(s); remove them before deleting"
            ),
        )

    await RequestRepository.delete(db, req)
    return success_response(data={"deleted": True}, message="Request deleted")