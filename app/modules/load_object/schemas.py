from app.utils.base_schema import CamelBaseModel
from typing import List, Dict, Optional
from app.database.staging.models import MaterialType
from datetime import date


class PoleSchema(CamelBaseModel):
    name: str
    diameter: float
    thickness: float
    material: MaterialType
    z_height: float


class DirectObjectSchema(CamelBaseModel):
    name: str
    area: float
    cf: float
    weight: float
    z_height: float

class OverheadWireSchema(CamelBaseModel):
    name: str
    weight: float
    z_height: float
    span: float
    diameter: float
    sagging_ratio: float
    nnc: float
    fix_angle: float
    vertical_angle: float


class ProjectSchema(CamelBaseModel):
    report_number: str
    project_title: str
    project_date: str
    request_number: str

class ConditionSchema(CamelBaseModel):
    design_standard: str
    design_wind_speed: float
    design_air_density: float

class LoadObjectRequest(CamelBaseModel):
    project: ProjectSchema
    condition: ConditionSchema
    poles: List[PoleSchema]
    high_evaluation: Dict[str, float]
    direct_objects: Optional[List[DirectObjectSchema]] = [] # Optional
    overhead_wires: Optional[List[OverheadWireSchema]] = [] # Optional
    session_id: Optional[str] = None


# RESULT SCHEMA CALCULATE
class ObjectResultSchema(CamelBaseModel):
    name: str
    windload: float
    moment: float

class LoadObjectResultData(CamelBaseModel):
    session_id: str
    status: str # ok, ng
    total_moment: float
    total_windload: float
    objects: List[ObjectResultSchema]

class LoadObjectResponse(CamelBaseModel):
    status: str 
    message: Optional[str] = None
    data: LoadObjectResultData

# RESULT SCHEMA GET Data

# tidak pelu di declare setiap object karena terlalu complex nanti
# class EvaluationObjectSchema(CamelBaseModel):
#     name: str
#     moment: float
#     windload: float

class HighEvalDetailSchema(CamelBaseModel):
    status: str
    total_moment: float 
    total_windload: float
    z_ref: float 
    objects: list


class ConditionSchema(CamelBaseModel):
    design_standard: str
    wind_speed: float
    air_density: float

class DatabaseProjectSchema(CamelBaseModel):
    title: str
    report_number: str
    date: date
    project_type: str

class StagingDataResponseSchema(CamelBaseModel):
    project: DatabaseProjectSchema
    condition: ConditionSchema
    # high_evaluations: Dict[str, HighEvalDetailSchema] 
    high_evaluations: list
