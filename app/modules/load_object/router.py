from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.response import success_response

# Import skema dan mapper spesifik load_object
from app.modules.load_object.schemas import LoadObjectRequest
from app.modules.load_object.entity_mapper import StagingEntityMapper

# Import komponen agnostik (General)
from app.staging.orchestrator import Orchestrator
from app.staging.mapper import Mapper 
from app.staging.repository import StagingRepository
from app.core.staging_database import get_db

from app.modules.load_object.schemas import StagingDataResponseSchema, LoadObjectResponse



routerLoadObject = APIRouter(prefix="/api/load-object", tags=["Load Object"])

@routerLoadObject.post("/calculate", response_model=LoadObjectResponse)
async def calculate_pole(payload: LoadObjectRequest, db:AsyncSession = Depends(get_db)):
    # Forward to Calculation after turn to snake_case format
    final_data = await Orchestrator.run_calculation_and_staging(
        payload=payload,
        db=db,
        calc_url="/api/load-object/calculate",
        to_pure_payload_func=Mapper.to_pure_calculation_payload,
        map_to_entity_func=StagingEntityMapper.map_to_entities,
        to_frontend_response_func=Mapper.to_frontend_response_layout,
        save_repository_func=StagingRepository.save_staging_transaction
    )
    return success_response(
        data=final_data["data"],
        message=final_data.get("message", "Calculation successful"),
        success=final_data.get("success", True),
        to_camel=True
    )


@routerLoadObject.get("/{session_id}", response_model=StagingDataResponseSchema)
async def get_calculation_data(session_id: str, db: AsyncSession = Depends(get_db)):
    data = await Orchestrator.get_staging_data(
        session_id=session_id,
        db=db,
        query_builder_func=StagingEntityMapper.build_load_object_query,
        format_response_func=StagingEntityMapper.format_load_object_response
    )
    
    if not data:
        raise HTTPException(status_code=404, detail="Session ID not found")
        
    return success_response(
        data=data,
        message="Staging data retrieved successfully",
        success=True,
        to_camel=True
    )