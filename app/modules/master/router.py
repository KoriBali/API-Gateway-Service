from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.response import success_response

from app.core.staging_database import get_db
from app.modules.master.repository import MasterRepository
from app.modules.master.schemas import (
    MaterialSchema,
    ObjectTypeSchema,
    CodeLabelSchema,
    DesignStandardSchema
)


routerMaster = APIRouter(prefix="/api/master", tags=["Master Data"])

@routerMaster.get("/ping")
async def ping():
    return success_response(
        data={
            "module" : "master",
            "status" : "alive"
            },
        message="Master module is working"
    )



# ===== Materials =====
@routerMaster.get("/materials")
async def get_materials(db: AsyncSession = Depends(get_db)):
    rows = await MasterRepository.list_materials(db)
    data = [MaterialSchema.model_validate(row) for row in rows]
    return success_response(data=data, message="Materials retrieved")



# ===== Object Types =====
@routerMaster.get("/object-types")
async def get_object_types(db: AsyncSession = Depends(get_db)):
    rows = await MasterRepository.list_object_types(db)
    data = [ObjectTypeSchema.model_validate(row) for row in rows]
    return success_response(data=data, message="Object Types retrieved")



# ===== Region Codes =====
@routerMaster.get("/region-codes")
async def get_region_codes(db: AsyncSession = Depends(get_db)):
    rows = await MasterRepository.list_region_codes(db)
    data = [CodeLabelSchema.model_validate(row) for row in rows]
    return success_response(data=data, message="Region Codes retrieved")



# ===== Department Codes =====
@routerMaster.get("/department-codes")
async def get_materials(db: AsyncSession = Depends(get_db)):
    rows = await MasterRepository.list_department_codes(db)
    data = [CodeLabelSchema.model_validate(row) for row in rows]
    return success_response(data=data, message="Department Codes retrieved")



# ===== Author Codes =====
@routerMaster.get("/author-codes")
async def get_materials(db: AsyncSession = Depends(get_db)):
    rows = await MasterRepository.list_author_codes(db)
    data = [CodeLabelSchema.model_validate(row) for row in rows]
    return success_response(data=data, message="Author Codes retrieved")



# ===== Lighting Company Codes =====
@routerMaster.get("/lighting-company-codes")
async def get_materials(db: AsyncSession = Depends(get_db)):
    rows = await MasterRepository.list_lighting_company_codes(db)
    data = [CodeLabelSchema.model_validate(row) for row in rows]
    return success_response(data=data, message="Lighting Company Codes retrieved")



# =====================
# Relational Database
# =====================


# ===== Design Standards =====
@routerMaster.get("/design-standards")
async def get_materials(
    category: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    rows = await MasterRepository.list_design_standards(db, category)
    data = [DesignStandardSchema.model_validate(row) for row in rows]
    return success_response(data=data, message="Design Standards retrieved")