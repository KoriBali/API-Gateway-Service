"""Body dan jawaban Project Tools calculation pole.

Sesi tool tidak pernah tersimpan: conditions dan isian dikirim utuh di setiap panggilan
(Hitung, preview laporan, Simpan). Simpan menulis semuanya ke request dalam satu transaksi.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from app.database.models.calculation import StatusCalculationRun
from app.database.models.intake import DesignType, RequestStatus
from app.modules.calculation.builder import BASE_ELEVATION_M
from app.modules.calculation.schemas import CalculationCaseFields, CalculationInput, StepPoleInput
from app.modules.intake.schemas import RequestCreate
from app.utils.base_schema import CamelBaseModel

# Skala kolom angka calculation_conditions: Numeric(10, 5).
_CONDITION_SCALE = Decimal("0.00001")


class PoleToolConditions(CamelBaseModel):
    """Conditions sesi tool. windSpeed wajib: tool tanpa angin tidak bisa menghitung.
    Nilai dibulatkan ke skala kolom, supaya conditions yang disimpan sama persis dengan
    yang dipakai Hitung dan run (tidak langsung basi)."""
    design_standard_id: str = Field(min_length=1)
    wind_speed: float = Field(gt=0)
    air_density: float = Field(gt=0)
    # Wajib untuk design standard yang memakai kondisi seismik (New JIL), selain itu boleh kosong.
    horizontal_acceleration: float | None = Field(default=None, gt=0)
    response_ratio: float | None = Field(default=None, gt=0)

    @field_validator("wind_speed", "air_density", "horizontal_acceleration", "response_ratio")
    @classmethod
    def _column_scale(cls, value: float | None) -> float | None:
        if value is None:
            return None
        rounded = Decimal(str(value)).quantize(_CONDITION_SCALE, rounding=ROUND_HALF_UP)
        if rounded <= 0:
            raise ValueError("must be greater than 0 after rounding to 5 decimals")
        return float(rounded)


class PoleToolInput(CalculationInput):
    """Isian tiang Project Tools. Seluruh geometri yang dibutuhkan Calculation Service dikirim
    di body (stepPoles, evaluatedPositionsM), jadi gateway cukup meneruskannya.

    poleStandardHeightId hanya penanda asal geometri:
    - terisi  = tiang standard. Geometri katalog pilihan tinggi itu (GET
      /api/master/pole-standard-heights/{id}/geometry) dipakai frontend sebagai nilai awal
      dan boleh diubah user.
    - kosong  = tiang custom, tanpa katalog.

    recopyCatalog tidak berlaku: case baru selalu menyalin katalog."""
    pole_standard_height_id: str | None = Field(default=None, min_length=1)
    step_poles: Annotated[list[StepPoleInput], Field(min_length=1)]
    # Elevasi (m) penampang yang dicek, dari dasar tiang.
    evaluated_positions_m: Annotated[list[float], Field(min_length=1)]
    recopy_catalog: Literal[False] = False

    @model_validator(mode="after")
    def _step_poles_unique(self):
        # Calculation Service menolak nama dan top elevation kembar (sama dengan unique constraint DB).
        names = [s.name for s in self.step_poles]
        if len(names) != len(set(names)):
            raise ValueError("stepPoles names must be unique")
        tops = [s.top_elevation_m for s in self.step_poles]
        if len(tops) != len(set(tops)):
            raise ValueError("stepPoles topElevationM must be unique")
        return self

    @model_validator(mode="after")
    def _evaluated_positions(self):
        # Aturan kontrak Calculation Service, ditolak di sini supaya pesannya jelas untuk user.
        positions = self.evaluated_positions_m
        if len(positions) != len(set(positions)):
            raise ValueError("evaluatedPositionsM must be unique")
        if any(p < BASE_ELEVATION_M for p in positions):
            raise ValueError(f"evaluatedPositionsM cannot be below the pole base ({BASE_ELEVATION_M} m)")
        top = max(s.top_elevation_m for s in self.step_poles)
        if any(p >= top for p in positions):
            raise ValueError(f"evaluatedPositionsM must be below the highest stepPoles topElevationM ({top} m)")
        return self


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
