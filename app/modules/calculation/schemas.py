from typing import Annotated

from pydantic import ConfigDict, StringConstraints, model_validator


from app.utils.base_schema import CamelBaseModel, snake_to_camel

from datetime import datetime

from app.database.models.calculation import PoleFamily, GroundPosition, PoleKind


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



# ===== Calculation Case =====
# Judul case. Kosong saat create = diisi dari requests.subject
CaseTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class CalculationCaseFields(CamelBaseModel):
    """Field skalar case yang diisi owner. Dipakai bersama Create dan Update."""
    title: CaseTitle | None = None
    pole_standard_id: str | None = None
    pole_standard_height_id: str | None = None
    pole_combination_id: str | None = None
    pole_family: PoleFamily | None = None
    ground_position: GroundPosition | None = None
    lowest_height: float | None = None
    embedment_length: float | None = None
    overdesign_factor: int | None = None
    case_label: str | None = None

    # TODO(calc-contract): komponen belum difinalkan. Skeleton pass-through.
    #   Dipetakan konkret ke CalculationOpening/BasePlate/Foundation di iterasi lanjut.
    openings: list[dict] | None = None
    baseplates: list[dict] | None = None
    foundations: list[dict] | None = None


class CalculationCaseCreate(CalculationCaseFields):
    # Dipilih drafter saat case dibuat, tanpa nilai bawaan
    pole_kind: PoleKind


class CalculationCaseUpdate(CalculationCaseFields):
    pole_kind: PoleKind | None = None

    @model_validator(mode="after")
    def _not_null(self):
        # Kolom NOT NULL: tidak dikirim boleh, dikirim null ditolak.
        for field in ("title", "pole_kind"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{snake_to_camel(field)} cannot be null")
        return self



class CalculationCaseRead(CamelBaseModel):
    id: str
    request_id: str
    created_by_user_id: str
    owner_user_id: str
    title: str
    case_label: str | None = None
    pole_kind: PoleKind
    pole_standard_id: str | None = None
    pole_standard_height_id: str | None = None
    pole_combination_id: str | None = None
    pole_family: PoleFamily | None = None
    ground_position: GroundPosition | None = None
    lowest_height: float | None = None
    embedment_length: float | None = None
    overdesign_factor: int | None = None
    created_at: datetime
    updated_at: datetime