from typing import Annotated, Any, Literal

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
    """Header case yang diisi owner: cangkang saja. Isian perhitungan (tinggi, objek
    langsung) hanya ditulis Simpan. Field lain di body diabaikan."""
    title: CaseTitle | None = None
    case_label: str | None = None


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
    """Isian satu halaman perhitungan tiang standard: pilihan tinggi dan objek langsung.
    Segmen tiang dan ground position tidak diterima: keduanya dari katalog pilihan tinggi."""
    pole_standard_height_id: str
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



# ===== Tampilan hasil =====
# Nilai mesin. Frontend menampilkan ok/ng sebagai O.K/N.G.
CheckStatus = Literal["ok", "ng"]


class PositionCheck(CamelBaseModel):
    """Hasil satu posisi cek pada arah tampilan design standard."""
    evaluated_position_m: float
    evaluated_pole_name: str
    utilization_ratio: float
    status: str


class CalculationDisplay(CamelBaseModel):
    # Sama dengan status run: ok bila seluruh pengecekan di semua posisi dan arah O.K.
    status: CheckStatus
    # Arah yang ditampilkan, mengikuti design standard run (Old JIL: N).
    # None = arah design standard ini belum ditentukan; positions kosong.
    display_direction: str | None = None
    positions: list[PositionCheck]



# ===== Data laporan =====
class ReportLoadRow(CamelBaseModel):
    """Satu baris tabel beban: objek langsung lalu segmen tiang."""
    kind: Literal["direct_object", "pole"]
    name: str
    unit_weight_n: float
    quantity: int
    fix_load_n: float
    projected_area_per_unit_m2: float
    wind_coefficient: float
    wind_load_per_unit_n: float
    wind_quantity: int
    wind_load_n: float


class ReportSection(CamelBaseModel):
    """Pemeriksaan satu posisi cek pada arah laporan."""
    evaluated_position_m: float
    pole_name: str
    material_name: str
    diameter_mm: float
    thickness_mm: float
    section_modulus_cm3: float
    rows: list[ReportLoadRow]
    vertical_load_n: float
    horizontal_load_n: float
    bending_moment_nm: float
    calculated_stress_n_mm2: float
    allowable_stress_n_mm2: float
    utilization_ratio: float
    status: CheckStatus


class ReportFoundationLoads(CamelBaseModel):
    """Gaya di dasar tiang: posisi cek terendah, arah laporan."""
    vertical_load_n: float
    horizontal_load_n: float
    bending_moment_nm: float
    

class ReportStepPole(CamelBaseModel):
    """Satu segmen tiang yang dihitung run. Bentuk sama dengan step_poles, tanpa id.
    Straight: ukuran di kolom lower, upper kosong."""
    name: str
    pole_type: PoleType
    material_name: str
    top_elevation_m: float
    diameter_lower_mm: float
    diameter_upper_mm: float | None = None
    thickness_lower_mm: float
    thickness_upper_mm: float | None = None


class ReportDirectObject(CamelBaseModel):
    """Satu objek langsung yang dihitung run. Bentuk sama dengan direct_objects, tanpa id."""
    name: str
    object_kind: ObjectKind
    front_area_m2: float
    side_area_m2: float | None = None
    fixed_angle_deg: float | None = None
    mass_per_unit_kg: float
    elevation_m: float
    base_wind_coefficient: float
    quantity: int


class ReportGeometry(CamelBaseModel):
    """Tiang dan objek langsung yang dihitung run, dari input_snapshot, bukan dari case saat ini."""
    pole_standard_name: str
    pole_standard_height: float
    ground_position: GroundPosition
    gl_elevation_m: float | None = None
    # Urut dari puncak tertinggi, sama dengan payload Calculation Service.
    step_poles: list[ReportStepPole]
    # Urut nama, sama dengan payload Calculation Service.
    direct_objects: list[ReportDirectObject]


class ReportOverallCheck(CamelBaseModel):
    """Status run dan pengecekan dengan rasio terbesar di semua posisi dan arah."""
    status: StatusCalculationRun
    evaluated_position_m: float
    direction: str
    utilization_ratio: float


class CalculationReport(CamelBaseModel):
    run_id: str
    template: str
    design_standard_code: int
    design_standard_name: str
    # Arah yang ditampilkan di bagian pemeriksaan.
    report_direction: str
    design_wind_speed_m_s: float
    wind_pressure_n_m2: float
    allowable_stress_n_mm2: float
    geometry: ReportGeometry
    # Urut dari posisi cek tertinggi.
    sections: list[ReportSection]
    foundation: ReportFoundationLoads
    overall: ReportOverallCheck



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
    # Disusun saat dibaca, tidak disimpan. None untuk run failed.
    display: CalculationDisplay | None = None


class RunNotCreated(CamelBaseModel):
    reason: str
    message: str


class CalculationSaveResult(CamelBaseModel):
    case: CalculationCaseDetail
    run: CalculationRunRead | None = None
    run_not_created: RunNotCreated | None = None


class CalculateResult(CamelBaseModel):
    """Hasil Hitung: status dan tampilan hasil. Payload dan jawaban mentah ada di run (Simpan)."""
    status: StatusCalculationRun
    display: CalculationDisplay