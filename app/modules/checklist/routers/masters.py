from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.database.models.workflow import WorkType
from app.modules.checklist.repository import MasterItemRepository
from app.modules.checklist.schemas import MasterItemCreate, MasterItemRead, MasterItemUpdate

routerChecklistMaster = APIRouter(prefix="/api/nc-checklist-item-masters", tags=["NC Checklist Master"])

# Daftar induk dimiliki superadmin. Pengisi checklist boleh membacanya.
_READ_ROLE = require_roles("superadmin", "admin_department", "drafter_checker")
_SUPERADMIN = require_roles("superadmin")



@routerChecklistMaster.get("")
async def list_master_items(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
    work_type: WorkType | None = Query(default=None, alias="workType"),
    include_inactive: bool = Query(default=False, alias="includeInactive"),
):
    rows = await MasterItemRepository.list_items(db, work_type=work_type, include_inactive=include_inactive)
    return success_response(
        data=[MasterItemRead.model_validate(r) for r in rows],
        message="Checklist master items retrieved",
    )


@routerChecklistMaster.post("")
async def create_master_item(
    payload: MasterItemCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_SUPERADMIN),
):
    row = await MasterItemRepository.create(db, payload.model_dump())
    return success_response(
        data=MasterItemRead.model_validate(row),
        status_code=status.HTTP_201_CREATED,
        message="Checklist master item created",
    )


# Tidak ada DELETE: item yang tidak dipakai lagi dinonaktifkan (isActive false), supaya
# jejak source_master_id di checklist lama tetap utuh.
@routerChecklistMaster.patch("/{master_id}")
async def update_master_item(
    master_id: str,
    payload: MasterItemUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_SUPERADMIN),
):
    row = await MasterItemRepository.get(db, master_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist master item not found")
    row = await MasterItemRepository.update(db, row, payload.model_dump(exclude_unset=True))
    return success_response(data=MasterItemRead.model_validate(row), message="Checklist master item updated")