from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.response import success_response

from app.core.database import get_db
from app.modules.master.repository import MasterRepository
from app.modules.master.schemas import (
    MaterialSchema,
    ObjectTypeSchema,
    CodeLabelSchema,
    DesignStandardSchema,
    PoleStandardSchema,
    RegionSchema,
    ExternalObjectAvailabilitySchema,
    ExternalObjectSchema,
    CouplingCaseSchema,
    CouplingPositionSchema,
    CouplingSizeSchema,
    CouplingTypeSchema
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
# @routerMaster.get("/materials")
# async def get_materials(db: AsyncSession = Depends(get_db)):
#     rows = await MasterRepository.list_materials(db)
#     data = [MaterialSchema.model_validate(row) for row in rows]
#     return success_response(data=data, message="Materials retrieved")



# ===== Object Types =====
# @routerMaster.get("/object-types")
# async def get_object_types(db: AsyncSession = Depends(get_db)):
#     rows = await MasterRepository.list_object_types(db)
#     data = [ObjectTypeSchema.model_validate(row) for row in rows]
#     return success_response(data=data, message="Object Types retrieved")



# ===== Region Codes =====
# @routerMaster.get("/region-codes")
# async def get_region_codes(db: AsyncSession = Depends(get_db)):
#     rows = await MasterRepository.list_region_codes(db)
#     data = [CodeLabelSchema.model_validate(row) for row in rows]
#     return success_response(data=data, message="Region Codes retrieved")



# ===== Department Codes =====
# @routerMaster.get("/department-codes")
# async def get_department_codes(db: AsyncSession = Depends(get_db)):
#     rows = await MasterRepository.list_department_codes(db)
#     data = [CodeLabelSchema.model_validate(row) for row in rows]
#     return success_response(data=data, message="Department Codes retrieved")



# ===== Author Codes =====
# @routerMaster.get("/author-codes")
# async def get_author_codes(db: AsyncSession = Depends(get_db)):
#     rows = await MasterRepository.list_author_codes(db)
#     data = [CodeLabelSchema.model_validate(row) for row in rows]
#     return success_response(data=data, message="Author Codes retrieved")



# ===== Lighting Company Codes =====
# @routerMaster.get("/lighting-company-codes")
# async def get_lighting_company_codes(db: AsyncSession = Depends(get_db)):
#     rows = await MasterRepository.list_lighting_company_codes(db)
#     data = [CodeLabelSchema.model_validate(row) for row in rows]
#     return success_response(data=data, message="Lighting Company Codes retrieved")



# =====================
# Relational Database
# =====================


# ===== Design Standards =====
@routerMaster.get("/design-standards")
async def get_design_standards(
    category: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    rows = await MasterRepository.list_design_standards(db, category)
    data = [DesignStandardSchema.model_validate(row) for row in rows]
    return success_response(data=data, message="Design Standards retrieved")



# ===== Pole Standard =====
@routerMaster.get("/pole-standards")
async def get_pole_standards(
    category: str | None = None,
    type: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    rows = await MasterRepository.list_pole_standards(db, category, type)
    data = [PoleStandardSchema.model_validate(row) for row in rows]
    result = success_response(data=data, message="Pole Standards retrieved")
    # Cahce Karena Data jarang berganti
    result.headers["Cache-Control"] = "public, max-age=3600"
    return result


# ===== BootStrap(aggregate) =====
@routerMaster.get("/bootstrap")
async def get_bootstrap(db: AsyncSession = Depends(get_db)):
    materials = await MasterRepository.list_materials(db)
    object_types = await MasterRepository.list_object_types(db)
    region_codes = await MasterRepository.list_region_codes(db)
    department_codes = await MasterRepository.list_department_codes(db)
    author_codes = await MasterRepository.list_author_codes(db)
    lighting_codes = await MasterRepository.list_lighting_company_codes(db)

    data = {
        "materials": [MaterialSchema.model_validate(x) for x in materials],
        "object_types": [ObjectTypeSchema.model_validate(x) for x in object_types],
        "region_codes": [CodeLabelSchema.model_validate(x) for x in region_codes],
        "department_codes": [CodeLabelSchema.model_validate(x) for x in department_codes],
        "author_codes": [CodeLabelSchema.model_validate(x) for x in author_codes],
        "lighting_company_codes": [CodeLabelSchema.model_validate(x) for x in lighting_codes],
    }
    result = success_response(data=data, message="Bootstrap master data retrieved")
    # Cahce Karena Data jarang berganti
    result.headers["Cache-Control"] = "public, max-age=3600"
    return result



@routerMaster.get("/regions")
async def get_regions(db: AsyncSession = Depends(get_db)):
    rows = await MasterRepository.list_regions(db)
    data = [RegionSchema.model_validate(r) for r in rows]
    return success_response(data=data, message="Regions retrieved")


@routerMaster.get("/external-objects")
async def get_external_objects(db: AsyncSession = Depends(get_db)):
    rows = await MasterRepository.list_external_objects(db)
    data = [ExternalObjectSchema.model_validate(r) for r in rows]
    return success_response(data=data, message="External objects retrieved")


@routerMaster.get("/external-object-availabilities")
async def get_eo_availabilities(db: AsyncSession = Depends(get_db)):
    rows = await MasterRepository.list_eo_availabilities(db)
    data = [ExternalObjectAvailabilitySchema.model_validate(r) for r in rows]
    return success_response(data=data, message="External object availabilities retrieved")


@routerMaster.get("/external-objects/available")
async def get_available_external_objects(
    region: str,
    angle: float = 0,
    db: AsyncSession = Depends(get_db),
):
    region_obj = await MasterRepository.get_region(db, region)
    if region_obj is None:
        raise HTTPException(status_code=404, detail=f"Region '{region}' not found")
    rows = await MasterRepository.resolve_external_objects(db, region_id=region_obj.id, is_zero=(angle == 0))
    data = [ExternalObjectSchema.model_validate(r) for r in rows]
    return success_response(data=data, message="Available external objects resolved")




# ===== Coupling Aggregate =====
@routerMaster.get("/coupling")
async def get_coupling(db: AsyncSession = Depends(get_db)):
    regions = await MasterRepository.list_regions(db)
    external_objects = await MasterRepository.list_external_objects(db)
    availabilities = await MasterRepository.list_eo_availabilities(db)
    positions = await MasterRepository.list_coupling_positions(db)
    sizes = await MasterRepository.list_coupling_sizes(db)
    types = await MasterRepository.list_coupling_types(db)
    cases = await MasterRepository.list_coupling_cases(db)

    data = {
        "regions": [RegionSchema.model_validate(x) for x in regions],
        "external_objects": [ExternalObjectSchema.model_validate(x) for x in external_objects],
        "external_object_availabilities": [ExternalObjectAvailabilitySchema.model_validate(x) for x in availabilities],
        "coupling_positions": [CouplingPositionSchema.model_validate(x) for x in positions],
        "coupling_sizes": [CouplingSizeSchema.model_validate(x) for x in sizes],
        "coupling_types": [CouplingTypeSchema.model_validate(x) for x in types],
        "coupling_cases": [CouplingCaseSchema.model_validate(x) for x in cases],
    }
    result = success_response(data=data, message="Coupling master data retrieved")
    # Cache karena data jarang berganti (sejajar pole-standards)
    result.headers["Cache-Control"] = "public, max-age=3600"
    return result