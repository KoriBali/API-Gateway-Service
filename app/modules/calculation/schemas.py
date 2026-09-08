from pydantic import ConfigDict

from app.utils.base_schema import CamelBaseModel, snake_to_camel

from datetime import datetime

from app.database.models.calculation import PoleFamily, GroundPosition


# ===== Calculate =====
class CalculateRequest(CamelBaseModel):
    # SKELETON - field domain BELUM difinalkan (menunggu kontrak calc-service + FE).
    # Pass-through longgar selama fase stub: terima payload apa adanya dari frontend.
    # TODO(calc-contract): ketatkan menjadi field eksplisit setelah kontrak final.
    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="allow",   # menerima field domain apa pun tanpa validasi
    )



# ===== Save Draft =====
class ConditionInput(CamelBaseModel):
    design_standard_id: str | None = None
    wind_speed: float | None = None
    air_density: float | None = None


class CalculationCaseUpsert(CamelBaseModel):
    title: str | None = None
    pole_standard_id: str | None = None
    pole_standard_height_id: str | None = None
    pole_combination_id: str | None = None
    pole_family: PoleFamily | None = None
    ground_position: GroundPosition | None = None
    lowest_height: float | None = None
    embedment_length: float | None = None
    overdesign_factor: int | None = None

    condition: ConditionInput | None = None

    # TODO(calc-contract): komponen belum difinalkan. Skeleton pass-through.
    #   Dipetakan konkret ke CalculationOpening/BasePlate/Foundation di iterasi lanjut.
    openings: list[dict] | None = None
    baseplates: list[dict] | None = None
    foundations: list[dict] | None = None


# ===== Save Draft =====
class CalculationCaseRead(CamelBaseModel):
    id: str
    request_id: str
    owner_user_id: str
    title: str
    pole_standard_id: str | None = None
    pole_standard_height_id: str | None = None
    pole_combination_id: str | None = None
    pole_family: PoleFamily | None = None
    ground_position: GroundPosition | None = None
    lowest_height: float | None = None
    embedment_length: float | None = None
    overdesign_factor: int | None = None
    condition: ConditionInput | None = None
    created_at: datetime
    updated_at: datetime