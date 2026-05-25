from typing import Callable, Any
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.services.calculation import forward

class Orchestrator:
    
    @staticmethod
    async def run_calculation_and_staging(
        payload: BaseModel, 
        db: AsyncSession,
        calc_url: str,
        to_pure_payload_func: Callable[[BaseModel], dict],
        map_to_entity_func: Callable[[BaseModel, dict], Any],
        to_frontend_response_func: Callable[[dict, str], dict],
        save_repository_func: Callable[[AsyncSession, Any], str]
    ) -> dict:
        """
        Mengorkestrasi alur pemisahan data, pemanggilan calculation dengan mempertahankan 
        konvensi message & success asli, dan penyimpanan ke staging database.
        """
        


        # 1. Pemisahan Payload via Mapper
        pure_calculation_payload = to_pure_payload_func(payload)
        
        # 2. Forward Pure Data ke Calculation Service
        result = await forward(calc_url, pure_calculation_payload)
        calculation_result = result.data if result.data else {}

        # 3. Translasi ke Entity Relational
        db_entity = map_to_entity_func(payload, calculation_result)
        
        # 4. Simpan ke Staging Layer
        session_id = await save_repository_func(db, db_entity)
        
        # 5. Susun susunan data untuk Response Frontend
        final_data = to_frontend_response_func(
            calculation_result=calculation_result,
            session_id=session_id
        )
        
        # 6. Bungkus kembali message dan success asli dari microservice
        return {
            "data": final_data,
            "message": result.message, 
            "success": result.success  
        }
    
    @staticmethod
    async def get_staging_data(
        session_id: str, 
        db: AsyncSession,
        query_builder_func: Callable[[str], Any],
        format_response_func: Callable[[Any], BaseModel]
    ):
        stmt = query_builder_func(session_id)
        
        result = await db.execute(stmt)
        data = result.scalar_one_or_none()
        
        if not data:
            return None
        
        response_data = format_response_func(data)
        return response_data.model_dump(mode="json")
    

    @staticmethod
    async def save_main_database(
        session_id: str,
        db: AsyncSession,
        get_staging_func: Callable[[str, AsyncSession], Any],
        # map_to_main_func: Callable[[Any], Any],
        # save_to_main_repo_func: Callable[[Any, AsyncSession], None]
    ):
        """
        Orchestrator agnostik untuk memindahkan data dari Staging ke Main DB.
        Bisa dipakai oleh load_object, base_plate, foundation, dll.
        """
        # 1. Ambil data dari Staging
        staging_data = await get_staging_func(session_id, db)
        if not staging_data:
            return None # Nanti di-handle oleh HTTP 404 di Router
            
        # 2. Ubah status
        staging_data.status = "save"
        
        # 3. Mapping data staging menjadi entitas Main DB
        # main_entities = map_to_main_func(staging_data)
        
        # 4. Save entitas ke Main DB 
        # await save_to_main_repo_func(main_entities, db)
        
        # 5. Eksekusi semua perubahan
        await db.commit()
        
        return True
    


    # Hapus data Staging
    async def delete_staging_data(
            session_id: str,
            db: AsyncSession,
            delete_repo_func: Callable[[str, AsyncSession], bool]
    )-> bool:
        
        success = await delete_repo_func(session_id, db)

        return success