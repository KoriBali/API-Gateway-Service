from typing import List
from app.utils.base_schema import CamelBaseModel


# ===== Flat Table Structure =====
class MaterialSchema (CamelBaseModel):
    id : str
    name : str
    is_active : bool


class ObjectTypeSchema (CamelBaseModel):
    id : str
    name : str
    is_active : bool


class CodeLabelSchema(CamelBaseModel):
    id : str
    code : str
    label : str
    is_active : bool


# ===== Relational Table Structure =====
class DesignStandardSchema(CamelBaseModel):
    id : str
    name : str
    default_wind_speed : float | None
    default_air_density : float | None
    is_active : bool


# ===== Pole Standard =====
class PoleThicknessSchema(CamelBaseModel):
    id : str
    position : str
    thickness : float

class PoleCombinationSchema(CamelBaseModel):
    id : str
    name : str
    pole_thicknesses : List[PoleThicknessSchema] = []

class PoleDiameterSchema(CamelBaseModel):
    id : str
    diameter : float
    pole_combinations : List[PoleCombinationSchema] = []

class PoleStandardHeightSchema(CamelBaseModel):
    id : str
    height : float

class PoleStandardSchema(CamelBaseModel):
    id : str
    name : str
    type : str
    geometry : dict | None = None
    pole_standard_heights : List[PoleStandardHeightSchema] = []
    pole_diameters : List[PoleDiameterSchema] = []