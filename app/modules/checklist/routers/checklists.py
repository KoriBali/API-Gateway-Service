from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.intake import permissions as intake_permissions
from app.modules.intake.repository import RequestRepository
from app.modules.workflow.repository import RequestEventRepository
from app.modules.workflow.gate import PRE_SUBMIT_STATUSES, current_checklist
from app.modules.assignment.permissions import WORK_TYPES_OF
from app.database.models.workflow import ChecklistItemStatus
from app.modules.checklist.repository import ChecklistRepository, MasterItemRepository
from app.modules.checklist.schemas import ChecklistItemRead, ChecklistItemUpdate, ChecklistRead

routerChecklist = APIRouter(prefix="/api/requests", tags=["NC Checklist"])

# Baca: pihak Koribali (yoshimoto_reviewer tidak). Isi: drafter_checker dan admin_department.
_READ_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")
_CHECKER_ROLE = require_roles("admin_department", "drafter_checker")



# ===== Helper =====
def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def _load_readable(db: AsyncSession, request_id: str, actor: CurrentUser, *, for_update: bool = False):
    if for_update:
        req = await RequestEventRepository.get_for_update(db, request_id)
    else:
        req = await RequestRepository.get_by_id(db, request_id)
    if req is None or not await intake_permissions.is_readable(db, actor, req):
        raise _not_found("Request")
    return req


def _ensure_pre_submit(req) -> None:
    """Checklist adalah bukti gerbang submit: hanya diubah sebelum request diajukan."""
    if req.status not in PRE_SUBMIT_STATUSES:
        raise _conflict(
            f"The checklist cannot be changed while the request is '{req.status.value}'. "
            "Allowed: internal, prevention_check"
        )


async def _current_id(db: AsyncSession, request_id: str) -> str | None:
    revision_round_id, _ = await RequestEventRepository.current_cycle(db, request_id)
    checklist = await current_checklist(db, request_id, revision_round_id)
    return checklist.id if checklist is not None else None


def _read(checklist, items, current_id) -> ChecklistRead:
    pending = sum(1 for i in items if i.item_status == ChecklistItemStatus.pending)
    return ChecklistRead(
        id=checklist.id,
        request_id=checklist.request_id,
        revision_round_id=checklist.revision_round_id,
        is_current=checklist.id == current_id,
        pending_count=pending,
        is_complete=pending == 0,
        items=[ChecklistItemRead.model_validate(i) for i in items],
    )



# ===== Read =====
@routerChecklist.get("/{request_id}/nc-checklists")
async def list_checklists(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    """Checklist semua siklus submit request ini, siklus pertama dulu."""
    await _load_readable(db, request_id, actor)
    checklists = await ChecklistRepository.list_for_request(db, request_id)
    items = await ChecklistRepository.items_of(db, [c.id for c in checklists])
    current_id = await _current_id(db, request_id)
    return success_response(
        data=[_read(c, items[c.id], current_id) for c in checklists],
        message="Checklists retrieved",
    )


@routerChecklist.get("/{request_id}/nc-checklists/current")
async def get_current_checklist(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    await _load_readable(db, request_id, actor)
    current_id = await _current_id(db, request_id)
    if current_id is None:
        raise _not_found("Checklist for the current submit cycle")
    checklist = await ChecklistRepository.get_in_request(db, request_id, current_id)
    items = await ChecklistRepository.items_of(db, [current_id])
    return success_response(data=_read(checklist, items[current_id], current_id), message="Checklist retrieved")



# ===== Buat checklist siklus berjalan (G6) =====
@routerChecklist.post("/{request_id}/nc-checklists")
async def create_checklist(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_CHECKER_ROLE),
):
    # Kunci request: status prevention_check dihitung ulang, dan dua pembuatan bersamaan
    # tidak menabrak unique (request_id, revision_round_id).
    req = await _load_readable(db, request_id, actor, for_update=True)
    _ensure_pre_submit(req)
    revision_round_id, _ = await RequestEventRepository.current_cycle(db, req.id)
    if await current_checklist(db, req.id, revision_round_id) is not None:
        raise _conflict("A checklist already exists for the current submit cycle")
    missing = await MasterItemRepository.work_types_without_active(db, WORK_TYPES_OF[req.design_type])
    if missing:
        raise _conflict(
            "No active checklist master items for workType "
            + ", ".join(f"'{wt.value}'" for wt in missing)
        )

    checklist = await ChecklistRepository.create_for_cycle(db, req, revision_round_id)
    items = await ChecklistRepository.items_of(db, [checklist.id])
    return success_response(
        data=_read(checklist, items[checklist.id], checklist.id),
        status_code=status.HTTP_201_CREATED,
        message="Checklist created",
    )



# ===== Isi item =====
@routerChecklist.patch("/{request_id}/nc-checklists/{checklist_id}/items/{item_id}")
async def update_checklist_item(
    request_id: str,
    checklist_id: str,
    item_id: str,
    payload: ChecklistItemUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_CHECKER_ROLE),
):
    # Kunci request: submit yang datang bersamaan menilai gerbang sesudah item ini tersimpan.
    req = await _load_readable(db, request_id, actor, for_update=True)
    checklist = await ChecklistRepository.get_in_request(db, request_id, checklist_id)
    if checklist is None:
        raise _not_found("Checklist")
    item = await ChecklistRepository.get_item(db, checklist_id, item_id)
    if item is None:
        raise _not_found("Checklist item")
    _ensure_pre_submit(req)
    if checklist.id != await _current_id(db, request_id):
        raise _conflict("Only the checklist of the current submit cycle can be changed")

    data = payload.model_dump(exclude_unset=True)
    start_at = data.get("start_at", item.start_at)
    finish_at = data.get("finish_at", item.finish_at)
    if start_at is not None and finish_at is not None and finish_at < start_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="finishAt must not be earlier than startAt",
        )

    item = await ChecklistRepository.update_item(db, item, data, actor_id=actor.id)
    return success_response(data=ChecklistItemRead.model_validate(item), message="Checklist item updated")