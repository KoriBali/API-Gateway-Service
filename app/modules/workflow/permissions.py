from fastapi import HTTPException, status

from app.database.models.intake import DesignType, Request, RequestStatus
from app.database.models.workflow import EventType


# Status asal yang sah untuk tiap peristiwa tingkat request
# "Pengisian status request oleh sistem"). Syarat isi gerbang submit dinilai di workflow/gate.py.
ALLOWED_FROM: dict[EventType, tuple[RequestStatus, ...]] = {
    EventType.submit: (RequestStatus.internal, RequestStatus.prevention_check),
    EventType.feedback: (RequestStatus.submitted,),
    EventType.clear: (RequestStatus.submitted,),
    EventType.reopen: (RequestStatus.cleared,),
    EventType.cancel: (
        RequestStatus.internal,
        RequestStatus.prevention_check,
        RequestStatus.submitted,
        RequestStatus.cleared,
    ),
}

# Status sesudah peristiwa.
RESULT_STATUS: dict[EventType, RequestStatus] = {
    EventType.submit: RequestStatus.submitted,
    EventType.feedback: RequestStatus.internal,
    EventType.clear: RequestStatus.cleared,
    EventType.reopen: RequestStatus.submitted,
    EventType.cancel: RequestStatus.canceled,
}



def ensure_status_allows(request: Request, event_type: EventType) -> None:
    """409 bila status request sekarang bukan status asal yang sah untuk peristiwa ini."""
    allowed = ALLOWED_FROM[event_type]
    if request.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot {event_type.value} a request with status '{request.status.value}'. "
                f"Allowed: {', '.join(s.value for s in allowed)}"
            ),
        )



def resolve_work_scope(request: Request, work_scope: DesignType | None) -> DesignType:
    """Work scope putaran Jepang harus berada di dalam requests.design_type."""
    if work_scope is None:
        return request.design_type
    if request.design_type == DesignType.drawing_calculation or work_scope == request.design_type:
        return work_scope
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"workScope must be within the request designType '{request.design_type.value}'",
    )