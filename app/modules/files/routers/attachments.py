from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.response import success_response
from app.modules.case import permissions as case_permissions
from app.modules.files import storage
from app.modules.files.repository import FileRepository
from app.modules.files.routers.files import resolve_file_name
from app.modules.files.schemas import file_read
from app.database.models.workflow import CheckResult, EventType, FileRole

routerAttachment = APIRouter(prefix="/api/requests", tags=["Request Files"])

# Pelaku peristiwa yang bisa membawa lampiran: feedback dan cancel (yoshimoto_reviewer),
# check (drafter_checker, admin_department). Pelaku persisnya dicek di handler.
_EVENT_ACTOR_ROLE = require_roles("admin_department", "drafter_checker", "yoshimoto_reviewer")
# Mengunggah berkas hasil pemeriksaan.
_CHECKER_ROLE = require_roles("admin_department", "drafter_checker")



def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)



# ===== Lampiran catatan =====
@routerAttachment.post("/{request_id}/events/{event_id}/attachments")
async def attach_to_event(
    request_id: str,
    event_id: str,
    file: UploadFile = File(...),
    file_name: str | None = Form(default=None, alias="fileName"),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_EVENT_ACTOR_ROLE),
):
    """Lampiran yang menyertai catatan sebuah peristiwa (note_attachment): feedback dari pihak
    Yoshimoto, koreksi internal (check dengan temuan), atau alasan pembatalan. Peristiwanya
    dicatat lebih dulu lewat endpoint peristiwa, lalu pelakunya melampirkan berkas di sini."""
    await case_permissions.load_readable_request(db, request_id, actor)
    events = await FileRepository.events_in_request(db, request_id, [event_id])
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    event = events[0]
    carries_note = event.event_type in (EventType.feedback, EventType.cancel) or (
        event.event_type == EventType.check and event.check_result == CheckResult.has_findings
    )
    if not carries_note:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attachments can only be added to feedback, cancel, or a check with findings",
        )
    if event.actor_user_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the actor of this event can attach files to it",
        )

    name = resolve_file_name(file_name, file)
    path = await storage.store_upload(request_id, file)
    try:
        row = await FileRepository.create_unversioned(
            db,
            request_id=request_id,
            uploader_id=actor.id,
            file_role=FileRole.note_attachment,
            request_event_id=event.id,
            file_name=name,
            storage_ref=path,
        )
    except Exception:
        await storage.discard([path])
        raise
    return success_response(
        data=file_read(row, [], None),
        status_code=status.HTTP_201_CREATED,
        message="Attachment uploaded",
    )



# ===== Berkas hasil pemeriksaan =====
@routerAttachment.post("/{request_id}/check-results")
async def upload_check_result(
    request_id: str,
    file: UploadFile = File(...),
    check_event_ids: list[str] = Form(alias="checkEventIds"),
    file_name: str | None = Form(default=None, alias="fileName"),
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_CHECKER_ROLE),
):
    """Satu berkas coretan pemeriksaan untuk satu case atau lebih. Pemeriksa memilih peristiwa
    check case yang tercakup; sistem membuat satu baris berkas per peristiwa (invariant berkas 7)."""
    await case_permissions.load_readable_request(db, request_id, actor)
    event_ids = list(dict.fromkeys(i for i in check_event_ids if i))
    if not event_ids:
        raise _unprocessable("checkEventIds must contain at least one check event")
    events = await FileRepository.events_in_request(db, request_id, event_ids)
    if len(events) != len(event_ids) or any(e.event_type != EventType.check for e in events):
        raise _unprocessable("checkEventIds must reference check events of this request")

    name = resolve_file_name(file_name, file)
    path = await storage.store_upload(request_id, file)
    try:
        rows = await FileRepository.create_check_results(
            db,
            request_id=request_id,
            uploader_id=actor.id,
            check_event_ids=event_ids,
            file_name=name,
            storage_ref=path,
        )
    except Exception:
        await storage.discard([path])
        raise
    return success_response(
        data=[file_read(row, [], None) for row in rows],
        status_code=status.HTTP_201_CREATED,
        message="Check result uploaded",
    )
