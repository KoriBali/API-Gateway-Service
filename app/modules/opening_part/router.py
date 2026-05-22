from fastapi import APIRouter
from app.modules.opening_part.schemas import OpeningPartRequest, OpeningPartResponse, OpeningPartResponseStatus
from app.services.calculation import forward

routerOpeningPart = APIRouter(prefix="/api/opening-part", tags=["Opening Part"])

@routerOpeningPart.post("/calculate", response_model=OpeningPartResponse)
async def calculate_opening_part(payload: OpeningPartRequest):
    return await forward("/api/opening-part/calculate", payload)


@routerOpeningPart.post("/calculate-status", response_model=OpeningPartResponseStatus)
async def calculate_opening_part_status(payload: OpeningPartRequest):
    return await forward("/api/opening-part/calculate-status", payload, "status")
