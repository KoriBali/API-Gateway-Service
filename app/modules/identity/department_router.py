from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.identity.repository import DepartmentRepository
from app.modules.identity.schemas import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentRead,
)

routerDepartment = APIRouter(prefix="/api/departments", tags=["Department"])


def _json(model) -> dict | list:
    return jsonable_encoder(model, by_alias=True)


# ===== Read (superadmin + admin) =====
@routerDepartment.get("")
async def list_departments(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin")),
):
    rows = await DepartmentRepository.list_all(db)
    data = [_json(DepartmentRead.model_validate(d)) for d in rows]
    return success_response(data=data, to_camel=False, message="Departments retrieved")


@routerDepartment.get("/{department_id}")
async def get_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin")),
):
    dept = await DepartmentRepository.get_by_id(db, department_id)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return success_response(
        data=_json(DepartmentRead.model_validate(dept)),
        to_camel=False,
        message="Department retrieved",
    )


# ===== Write (superadmin only) =====
@routerDepartment.post("")
async def create_department(
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin")),
):
    if await DepartmentRepository.get_by_code(db, payload.code):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department code already exists")
    if await DepartmentRepository.get_by_name(db, payload.name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department name already exists")

    dept = await DepartmentRepository.create(db, payload)
    return success_response(
        data=_json(DepartmentRead.model_validate(dept)),
        to_camel=False,
        status_code=status.HTTP_201_CREATED,
        message="Department created",
    )


@routerDepartment.patch("/{department_id}")
async def update_department(
    department_id: str,
    payload: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin")),
):
    dept = await DepartmentRepository.get_by_id(db, department_id)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    data = payload.model_dump(exclude_unset=True)

    # Cek unique HANYA bila nilai benar-benar berubah
    if "code" in data and data["code"] != dept.code:
        if await DepartmentRepository.get_by_code(db, data["code"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department code already exists")
    if "name" in data and data["name"] != dept.name:
        if await DepartmentRepository.get_by_name(db, data["name"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department name already exists")

    updated = await DepartmentRepository.update(db, dept, payload)
    return success_response(
        data=_json(DepartmentRead.model_validate(updated)),
        to_camel=False,
        message="Department updated",
    )


# ===== Delete (guarded, superadmin only) =====
@routerDepartment.delete("/{department_id}")
async def delete_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin")),
):
    dept = await DepartmentRepository.get_by_id(db, department_id)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    user_count, request_count = await DepartmentRepository.count_usage(db, department_id)
    if user_count > 0 or request_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Department still has {user_count} user(s) and {request_count} request(s); "
                "reassign or remove them before deleting"
            ),
        )

    await DepartmentRepository.delete(db, dept)
    return success_response(data={"deleted": True}, message="Department deleted")