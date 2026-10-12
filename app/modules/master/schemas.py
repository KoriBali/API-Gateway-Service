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



# ===== Coupling =====
class RegionSchema(CamelBaseModel):
    id: str
    code: str
    label: str
    # frequency_hz: int | None
    is_active: bool

class ExternalObjectSchema(CamelBaseModel):
    id: str
    code: str
    label: str
    is_active: bool

class ExternalObjectAvailabilitySchema(CamelBaseModel):
    id: str
    region_id: str
    external_object_id: str
    avail_when_zero: bool
    avail_when_nonzero: bool

# opsional 
class CouplingCaseSchema(CamelBaseModel):
    id: str
    case_number: int
    num_groups: int
    cp1_shape: str
    cp2_shape: str | None
    cp1_label: str | None
    cp2_label: str | None
    image_url: str | None
    detail_image_url: str | None
    is_active: bool

class CouplingPositionSchema(CamelBaseModel):
    id: str
    code: str
    label: str
    is_active: bool


class CouplingSizeSchema(CamelBaseModel):
    id: str
    code: str
    label: str
    is_active: bool


class CouplingTypeSchema(CamelBaseModel):
    id: str
    code: str
    label: str
    is_active: bool