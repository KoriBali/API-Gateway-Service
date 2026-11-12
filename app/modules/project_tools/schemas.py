"""Body dan jawaban Project Tools calculation pole.

Sesi tool tidak pernah tersimpan: conditions dan isian dikirim utuh di setiap panggilan
(Hitung, preview laporan, Simpan). Simpan menulis semuanya ke request dalam satu transaksi.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.database.models.calculation import StatusCalculationRun
from app.database.models.intake import DesignType, RequestStatus
from app.modules.calculation.schemas import CalculationCaseFields, CalculationInput
from app.modules.intake.schemas import RequestCreate
from app.utils.base_schema import CamelBaseModel

# Skala kolom calculation_conditions.wind_speed dan air_density: Numeric(10, 5).
_CONDITION_SCALE = Decimal("0.00001")


class PoleToolConditions(CamelBaseModel):
    """Conditions sesi tool. windSpeed wajib: tool tanpa angin tidak bisa menghitung.
    Nilai dibulatkan ke skala kolom, supaya conditions yang disimpan sama persis dengan
    yang dipakai Hitung dan run (tidak langsung basi)."""
    design_standard_id: str = Field(min_length=1)
    wind_speed: float = Field(gt=0)
    air_density: float = Field(gt=0)

    @field_validator("wind_speed", "air_density")
    @classmethod
    def _column_scale(cls, value: float) -> float:
        rounded = Decimal(str(value)).quantize(_CONDITION_SCALE, rounding=ROUND_HALF_UP)
        if rounded <= 0:
            raise ValueError("must be greater than 0 after rounding to 5 decimals")
        return float(rounded)


class PoleToolInput(CalculationInput):
    """Isian tiang sama dengan Hitung/Simpan case. recopyCatalog tidak berlaku: case baru
    selalu menyalin katalog."""
    recopy_catalog: Literal[False] = False


class PoleToolSession(CamelBaseModel):
    """Body Hitung dan preview laporan."""
    conditions: PoleToolConditions
    input: PoleToolInput


class PoleToolNewRequest(RequestCreate):
    """Body create request tanpa assignments: pengerjanya user yang menekan Simpan."""

    @model_validator(mode="before")
    @classmethod
    def _reject_assignments(cls, data):
        if isinstance(data, dict) and "assignments" in data:
            raise ValueError("assignments cannot be sent; the user who saves is assigned to calculation")
        return data

    @model_validator(mode="before")
    @classmethod
    def _reject_cover_upload(cls, data):
        if isinstance(data, dict) and ({"coverUploadId", "cover_upload_id"} & data.keys()):
            raise ValueError("coverUploadId cannot be sent here; save the cover with POST /api/requests")
        return data

    @model_validator(mode="after")
    def _includes_calculation(self):
        if self.design_type == DesignType.drawing:
            raise ValueError("designType must include calculation")
        return self


class PoleToolSave(PoleToolSession):
    """Body Simpan: tepat satu tujuan, request yang sudah ada atau request baru."""
    request_id: str | None = Field(default=None, min_length=1)
    new_request: PoleToolNewRequest | None = None
    # Judul kosong = requests.subject, sama dengan create case.
    case: CalculationCaseFields = Field(default_factory=CalculationCaseFields)

    @model_validator(mode="after")
    def _one_target(self):
        if (self.request_id is None) == (self.new_request is None):
            raise ValueError("Send exactly one of requestId or newRequest")
        return self


class PoleToolSaveResult(CamelBaseModel):
    request_id: str
    request_created: bool
    # Status request sesudah Simpan (internal atau prevention_check dihitung ulang).
    request_status: RequestStatus
    assignment_created: bool
    conditions_created: bool
    case_id: str
    run_id: str
    run_status: StatusCalculationRun
