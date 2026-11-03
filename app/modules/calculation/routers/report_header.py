from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.utils.base_schema import snake_to_camel
from app.utils.response import success_response
from app.modules.case import permissions as case_permissions
from app.modules.calculation.repository import CalculationCaseRepository, ReportHeaderRepository
from app.modules.calculation.schemas import ReportHeaderRead, ReportHeaderWrite
from app.database.models.intake import RequestStatus

routerReportHeader = APIRouter(prefix="/api/requests", tags=["Calculation"])

_READ_ROLE = require_roles("superadmin", "admin_department", "drafter_checker", "drafter")
_WORKER_ROLE = require_roles("admin_department", "drafter_checker", "drafter")

# Request yang sudah selesai atau dibatalkan: header tidak boleh berubah lagi.
# Request yang di-reopen kembali ke submitted, jadi header bisa diubah lagi.
_CLOSED_STATUSES = (RequestStatus.cleared, RequestStatus.canceled)



# ===== Read =====
@routerReportHeader.get("/{request_id}/calculation-cases/{case_id}/report-header")
async def get_report_header(
    request_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_READ_ROLE),
):
    await case_permissions.load_readable_request(db, request_id, actor)
    case = await CalculationCaseRepository.get_in_request(db, request_id, case_id)
    if case is None:
        raise case_permissions.case_not_found()
    header = await ReportHeaderRepository.get(db, case.id)
    if header is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report header not found")
    return success_response(
        data=ReportHeaderRead.model_validate(header),
        message="Report header retrieved",
    )



# ===== Buat atau ganti (owner saja) =====
@routerReportHeader.put("/{request_id}/calculation-cases/{case_id}/report-header")
async def put_report_header(
    request_id: str,
    case_id: str,
    payload: ReportHeaderWrite,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(_WORKER_ROLE),
):
    req = await case_permissions.load_readable_request(db, request_id, actor)
    # Kunci case: PUT pertama yang bersamaan tidak sama-sama meng-insert.
    case = await CalculationCaseRepository.get_in_request(db, request_id, case_id, for_update=True)
    if case is None:
        raise case_permissions.case_not_found()
    case_permissions.ensure_owner(actor, case)
    if req.status in _CLOSED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "request_closed",
                "message": f"The report header cannot be changed while the request is {req.status.value}",
            },
        )

    data = payload.model_dump()
    invalid = await ReportHeaderRepository.inactive_code_fields(db, data)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=", ".join(snake_to_camel(f) for f in invalid) + " does not reference an active code",
        )

    header, created = await ReportHeaderRepository.put(db, case.id, data)
    return success_response(
        data=ReportHeaderRead.model_validate(header),
        status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        message="Report header created" if created else "Report header saved",
    )
