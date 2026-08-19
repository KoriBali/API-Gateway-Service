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

