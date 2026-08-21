from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.response import success_response

# Import skema dan mapper spesifik load_object
from app.modules.load_object.schemas import LoadObjectRequest
from app.modules.load_object.entity_mapper import StagingEntityMapper

# Import komponen agnostik (General)
from app.database.orchestrator import Orchestrator
from app.database.mapper import Mapper 
from app.database.repository import StagingRepository
from app.core.database import get_db

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


# Save to Main Database (soon)
@routerLoadObject.post("/{session_id}/save")
async def staging_to_main(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Endpoint untuk memindahkan data dari Staging DB ke Main DB
    serta merubah status project menjadi 'save'.
    """
    
    # TODO: Panggil fungsi Orchestrator atau Service di sini nantinya
    # await Orchestrator.save_main_database(session_id=session_id, db=db)

    success = await Orchestrator.save_main_database(
        session_id=session_id,
        db=db,
        get_staging_func=StagingRepository.get_staging_project_by_id, 
        # map_to_main_func=MainDBEntityMapper.map_staging_to_main, 
        # save_to_main_repo_func=LoadObjectMainRepository.save_main_entities
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session ID not found in staging")
    
    # ==========================================
    # [MOCKUP / COMMENTED LOGIC FLOW]
    # ==========================================
    
    # 1. VALIDATE & GET DATA FROM STAGING
    # project_staging = await db.execute(select(StagingProject).where(StagingProject.id == session_id))
    # staging_data = project_staging.scalar_one_or_none()
    # if not staging_data:
    #     raise HTTPException(status_code=404, detail="Session ID not found in staging")
    
    # 2. UPDATE STATUS
    # staging_data.status = "save" # Awalnya "pending"
    
    # 3. MAP TO MAIN DB ENTITIES
    # main_db_entities = MainEntityMapper.map_from_staging(staging_data)
    
    # 4. INSERT TO MAIN DB 
    # (Asumsi memiliki koneksi atau async session ke engine Main DB jika dipisah, 
    # atau menggunakan session yang sama jika masih satu engine beda schema)
    # main_db_session.add_all(main_db_entities)
    
    # 5. CLEANUP (Optional: Hapus data dari staging agar tabel tidak bengkak)
    # await db.delete(staging_data)
    
    # 6. COMMIT TRANSACTIONS
    # await db.commit()
    # await main_db_session.commit()
    
    # ==========================================

    return success_response(
        data={
            "sessionId": session_id,
            "status": "save"
        },
        message="Project calculation data successfully saved to main database",
        success=True,
        to_camel=True
    )



# Delete data Staging
@routerLoadObject.delete("/{session_id}")
async def delete_calcultion_data(session_id:str, db:AsyncSession = Depends(get_db)):

    success = await Orchestrator.delete_staging_data(
        session_id=session_id,
        db=db,
        delete_repo_func=StagingRepository.delete_staging_project
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session ID not found from staging data")
    

    return success_response(
        data={"session_id": session_id},
        message="Stagging Project data successfully deleted",
        success=True,
        to_camel=True
    )