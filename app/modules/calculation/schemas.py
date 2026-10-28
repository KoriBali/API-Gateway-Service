from typing import Annotated, Any

from pydantic import StringConstraints, model_validator


from app.utils.base_schema import CamelBaseModel, snake_to_camel

from datetime import datetime

from app.database.models.calculation import (
    CalculationRunType,
    GroundPosition,
    PoleFamily,
    PoleKind,
    StatusCalculationRun,
)
from app.database.models.geometry import ObjectKind, PoleType



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



# ===== Input perhitungan (Hitung dan Simpan) =====
ObjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class DirectObjectInput(CamelBaseModel):
    """Satu objek langsung. Nama di-trim. Nilai numerik divalidasi Calculation Service."""
    name: ObjectName
    object_kind: ObjectKind
    front_area_m2: float
    side_area_m2: float | None = None
    fixed_angle_deg: float | None = None
    mass_per_unit_kg: float
    elevation_m: float
    base_wind_coefficient: float
    quantity: int

    @model_validator(mode="after")
    def _kind_dimensions(self):
        # Sama dengan CHECK object_kind_dimensions, supaya ditolak 422 sebelum ke DB.
        has_side = self.side_area_m2 is not None
        has_angle = self.fixed_angle_deg is not None
        if self.object_kind == ObjectKind.omni and (has_side or has_angle):
            raise ValueError("omni objects cannot have sideAreaM2 or fixedAngleDeg")
        if self.object_kind == ObjectKind.directional and not (has_side and has_angle):
            raise ValueError("directional objects require sideAreaM2 and fixedAngleDeg")
        return self


class CalculationInput(CamelBaseModel):
    """Isian satu halaman perhitungan tiang standard. Segmen tiang tidak diterima:
    selalu dari katalog pilihan tinggi."""
    pole_standard_height_id: str
    ground_position: GroundPosition
    overdesign_factor: int | None = None
    direct_objects: list[DirectObjectInput]
    # Simpan saja: salin ulang segmen dan posisi cek dari katalog walau tinggi tidak berubah (G1).
    recopy_catalog: bool = False

    @model_validator(mode="after")
    def _unique_names(self):
        names = [o.name for o in self.direct_objects]
        if len(names) != len(set(names)):
            raise ValueError("directObjects names must be unique")
        return self



# ===== Geometri case =====
class StepPoleRead(CamelBaseModel):
    id: str
    name: str
    material_id: str
    pole_type: PoleType
    top_elevation_m: float
    diameter_lower_mm: float
    diameter_upper_mm: float | None = None
    thickness_lower_mm: float
    thickness_upper_mm: float | None = None
    quantity: int


class DirectObjectRead(CamelBaseModel):
    id: str
    name: str
    object_kind: ObjectKind
    front_area_m2: float
    side_area_m2: float | None = None
    fixed_angle_deg: float | None = None
    mass_per_unit_kg: float
    elevation_m: float
    base_wind_coefficient: float
    quantity: int


class CalculationCaseDetail(CalculationCaseRead):
    """GET satu case dan hasil Simpan: case beserta isi perhitungannya."""
    evaluated_positions_m: list[float] | None = None
    step_poles: list[StepPoleRead] = []
    direct_objects: list[DirectObjectRead] = []
    # Keterangan, bukan palang. None = bukan tiang standard atau belum pilih tinggi.
    geometry_differs_from_catalog: bool | None = None



# ===== Run =====
class CalculationRunSummary(CamelBaseModel):
    id: str
    calculation_case_id: str
    run_type: CalculationRunType
    parent_run_id: str | None = None
    status: StatusCalculationRun
    run_by_user_id: str
    run_at: datetime


class CalculationRunRead(CalculationRunSummary):
    input_snapshot: dict[str, Any]
    result_snapshot: dict[str, Any] | None = None
    error_snapshot: dict[str, Any] | None = None


class RunNotCreated(CamelBaseModel):
    reason: str
    message: str


class CalculationSaveResult(CamelBaseModel):
    case: CalculationCaseDetail
    run: CalculationRunRead | None = None
    run_not_created: RunNotCreated | None = None


class CalculateResult(CamelBaseModel):
    """Hasil Hitung. Tampilan hasil (formatter) menyusul di Milestone 03."""
    status: StatusCalculationRun
    engine_request: dict[str, Any]
    engine_result: dict[str, Any]