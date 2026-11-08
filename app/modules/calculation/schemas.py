from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator, field_validator

from app.utils.base_schema import CamelBaseModel, snake_to_camel

from datetime import datetime

from app.database.models.calculation import (
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
    embedment_length_mm: float | None = None
    overdesign_factor: float | None = None
    # Terakhir kali Simpan menyimpan isian. Run yang lebih tua sudah basi.
    input_saved_at: datetime | None = None
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


class OverheadWireInput(CamelBaseModel):
    """Satu kawat udara. Nilai numerik divalidasi Calculation Service."""
    name: ObjectName
    mass_per_length_kg_m: float
    diameter_mm: float
    elevation_m: float
    span_length_m: float
    # Persen, misalnya 3.
    sag_ratio_percent: float
    base_wind_coefficient: float
    fixed_angle_deg: float = 0
    vertical_angle_deg: float = 0


class ArmObjectInput(CamelBaseModel):
    """Satu objek di lengan. Arah hadapnya mengikuti lengan."""
    name: ObjectName
    object_kind: ObjectKind
    front_area_m2: float
    side_area_m2: float | None = None
    mass_per_unit_kg: float
    horizontal_load_distance_m: float
    base_wind_coefficient: float
    quantity: int

    @model_validator(mode="after")
    def _kind_dimensions(self):
        # Sama dengan CHECK object_kind_dimensions, supaya ditolak 422 sebelum ke DB.
        has_side = self.side_area_m2 is not None
        if self.object_kind == ObjectKind.omni and has_side:
            raise ValueError("omni arm objects cannot have sideAreaM2")
        if self.object_kind == ObjectKind.directional and not has_side:
            raise ValueError("directional arm objects require sideAreaM2")
        return self


class ArmInput(CamelBaseModel):
    """Satu lengan. Badan lengan dihitung Calculation Service, tidak dikirim sebagai objek."""
    name: ObjectName
    material_id: str
    diameter_mm: float
    thickness_mm: float
    total_length_m: float
    exposed_length_m: float
    installation_height_m: float
    fixed_angle_deg: float = 0
    objects: list[ArmObjectInput] = []

    @model_validator(mode="after")
    def _unique_object_names(self):
        names = [o.name for o in self.objects]
        if len(names) != len(set(names)):
            raise ValueError("arm objects names must be unique within an arm")
        return self


class CalculationInput(CamelBaseModel):
    """Isian satu halaman perhitungan tiang standard: pilihan tinggi dan beban tiang.
    Selain tiang, semuanya boleh kosong. Step pole tidak diterima: dari katalog pilihan tinggi."""
    pole_standard_height_id: str
    direct_objects: list[DirectObjectInput]
    overhead_wires: list[OverheadWireInput] = []
    arms: list[ArmInput] = []
    # Kosong = bawaan baris katalog. embedment = tanpa baseplate, hanya untuk baris on_gl
    # (builder.GROUND_POSITION_CHOICES). Keduanya tidak dikirim ke Calculation Service.
    ground_position: GroundPosition | None = None
    embedment_length_mm: float | None = Field(default=None, gt=0)
    # Simpan saja: salin ulang step pole dan posisi cek dari katalog walau tinggi tidak berubah.
    recopy_catalog: bool = False

    @model_validator(mode="after")
    def _embedment_length(self):
        # Sama dengan CHECK embedment_length_mm, supaya ditolak 422 sebelum ke DB.
        if self.embedment_length_mm is not None and self.ground_position != GroundPosition.embedment:
            raise ValueError("embedmentLengthMm is only allowed when groundPosition is embedment")
        return self

    @model_validator(mode="after")
    def _unique_names(self):
        for field, rows in (
            ("directObjects", self.direct_objects),
            ("overheadWires", self.overhead_wires),
            ("arms", self.arms),
        ):
            names = [row.name for row in rows]
            if len(names) != len(set(names)):
                raise ValueError(f"{field} names must be unique")
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


class OverheadWireRead(CamelBaseModel):
    id: str
    name: str
    mass_per_length_kg_m: float
    diameter_mm: float
    elevation_m: float
    span_length_m: float
    sag_ratio_percent: float
    base_wind_coefficient: float
    fixed_angle_deg: float
    vertical_angle_deg: float


class ArmObjectRead(CamelBaseModel):
    id: str
    name: str
    object_kind: ObjectKind
    front_area_m2: float
    side_area_m2: float | None = None
    mass_per_unit_kg: float
    horizontal_load_distance_m: float
    base_wind_coefficient: float
    quantity: int


class ArmRead(CamelBaseModel):
    id: str
    name: str
    material_id: str
    diameter_mm: float
    thickness_mm: float
    total_length_m: float
    exposed_length_m: float
    installation_height_m: float
    fixed_angle_deg: float
    # Dinamai sama dengan body Hitung/Simpan. Dibaca dari relasi arm_objects.
    objects: list[ArmObjectRead] = Field(default=[], validation_alias="arm_objects")


class CalculationCaseDetail(CalculationCaseRead):
    """GET satu case dan hasil Simpan: case beserta isi perhitungannya."""
    evaluated_positions_m: list[float] | None = None
    step_poles: list[StepPoleRead] = []
    direct_objects: list[DirectObjectRead] = []
    overhead_wires: list[OverheadWireRead] = []
    arms: list[ArmRead] = []
    # Keterangan, bukan palang. None = bukan tiang standard atau belum pilih tinggi.
    geometry_differs_from_catalog: bool | None = None



# ===== Tampilan hasil =====
# Nilai mesin. Frontend menampilkan ok/ng sebagai OK/NG.
CheckStatus = Literal["ok", "ng"]


class DisplayCheck(CamelBaseModel):
    """Satu pengecekan kekuatan, apa adanya dari Calculation Service. Tiang: per posisi
    cek dan wind case. Lengan: per lengan, tanpa posisi cek dan wind case."""
    component: str
    # Step pole di posisi cek, atau nama lengan.
    name: str
    evaluated_position_m: float | None = None
    wind_case: str | None = None
    check: str
    utilization_ratio: float
    # Teks Calculation Service: "OK" / "NG".
    status: str


class DisplayGoverning(CamelBaseModel):
    """Pengecekan dengan utilization_ratio terbesar (summary.governing)."""
    component: str
    name: str
    evaluated_position_m: float | None = None
    wind_case: str | None = None
    check: str
    utilization_ratio: float


class CalculationDisplay(CamelBaseModel):
    # Sama dengan status run: ng bila ada satu pengecekan NG.
    status: CheckStatus
    governing: DisplayGoverning
    checks: list[DisplayCheck]



# ===== Data laporan =====
class ReportLoadRow(CamelBaseModel):
    """Satu baris tabel beban, apa adanya dari load_rows. Urutan Calculation Service:
    lengan, objek langsung, kawat udara, lalu step pole dari atas."""
    kind: Literal["arm", "direct_object", "overhead_wire", "pole"]
    name: str
    quantity: int
    fix_load_n: float
    # Lengan: null; nilainya ada per objek lengan.
    projected_area_m2: float | None = None
    wind_coefficient: float | None = None
    wind_load_n: float
    load_center_height_m: float
    wind_moment_nm: float | None = None
    # Kawat udara saja.
    wind_tension_n: float | None = None


class ReportSection(CamelBaseModel):
    """Pemeriksaan tiang di satu posisi cek pada wind case laporan."""
    evaluated_position_m: float
    pole_name: str
    material_name: str
    diameter_mm: float
    thickness_mm: float
    section_modulus_cm3: float
    rows: list[ReportLoadRow]
    vertical_load_n: float
    wind_load_n: float
    wind_tension_n: float
    horizontal_load_n: float
    arm_fix_load_moment_nm: float
    combined_moment_x_nm: float
    combined_moment_y_nm: float
    bending_moment_nm: float
    calculated_stress_n_mm2: float
    allowable_stress_n_mm2: float
    utilization_ratio: float
    status: CheckStatus


class ReportSpecification(CamelBaseModel):
    """Sifat penampang satu step pole atau satu lengan, apa adanya dari Calculation Service.
    Step pole diukur di diameter dan tebal bawahnya; ada untuk setiap step pole, termasuk
    yang tanpa posisi cek."""
    # pole atau arm, sama dengan DisplayCheck.component.
    component: str
    name: str
    # Lengan: null.
    pole_type: PoleType | None = None
    material_name: str
    diameter_mm: float
    thickness_mm: float
    cross_section_area_cm2: float
    moment_of_inertia_cm4: float
    radius_of_gyration_cm: float
    unit_weight_kg_m: float


class ReportFoundationLoads(CamelBaseModel):
    """Gaya di dasar tiang: posisi cek terendah, arah laporan."""
    vertical_load_n: float
    horizontal_load_n: float
    bending_moment_nm: float
    

class ReportStepPole(CamelBaseModel):
    """Satu step pole yang dihitung run. Bentuk sama dengan step_poles, tanpa id.
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
    
    
class ReportOverheadWire(CamelBaseModel):
    """Satu kawat udara yang dihitung run. Bentuk sama dengan overhead_wires, tanpa id."""
    name: str
    mass_per_length_kg_m: float
    diameter_mm: float
    elevation_m: float
    span_length_m: float
    sag_ratio_percent: float
    base_wind_coefficient: float
    fixed_angle_deg: float
    vertical_angle_deg: float


class ReportArmObject(CamelBaseModel):
    """Satu objek lengan yang dihitung run. Bentuk sama dengan arm_objects, tanpa id."""
    name: str
    object_kind: ObjectKind
    front_area_m2: float
    side_area_m2: float | None = None
    mass_per_unit_kg: float
    horizontal_load_distance_m: float
    base_wind_coefficient: float
    quantity: int


class ReportArm(CamelBaseModel):
    """Satu lengan yang dihitung run. Bentuk sama dengan arms, tanpa id."""
    name: str
    material_name: str
    diameter_mm: float
    thickness_mm: float
    total_length_m: float
    exposed_length_m: float
    installation_height_m: float
    fixed_angle_deg: float
    objects: list[ReportArmObject]


class ReportGeometry(CamelBaseModel):
    """Tiang dan beban yang dihitung run, dari input_snapshot, bukan dari case saat ini."""
    pole_standard_name: str
    pole_standard_height: float
    ground_position: GroundPosition
    gl_elevation_m: float | None = None
    # Isian laporan, bukan bagian payload. None bila bukan embedment atau tidak diisi.
    embedment_length_mm: float | None = None
    # Urut dari puncak tertinggi, sama dengan payload Calculation Service.
    step_poles: list[ReportStepPole]
    # Urut nama, sama dengan payload Calculation Service.
    direct_objects: list[ReportDirectObject]
    overhead_wires: list[ReportOverheadWire]
    arms: list[ReportArm]


class ReportOverallCheck(DisplayGoverning):
    """Status run dan pengecekan penentu di semua posisi cek, wind case, dan lengan."""
    status: StatusCalculationRun


class ReportArmSpecification(CamelBaseModel):
    section_area_cm2: float
    section_modulus_cm3: float
    moment_of_inertia_cm4: float
    radius_of_gyration_cm: float
    unit_weight_kg_m: float
    mass_kg: float
    fix_load_n: float
    front_projected_area_m2: float
    center_length_m: float


class ReportArmLoad(CamelBaseModel):
    """Satu baris beban lengan, apa adanya. Baris pertama badan lengan (ArmBody),
    lalu objek dari yang terjauh."""
    name: str
    object_type: str
    quantity: int
    fix_load_n: float
    front_projected_area_m2: float
    wind_coefficient: float
    front_wind_load_n: float
    horizontal_load_distance_m: float
    fix_load_moment_nm: float
    wind_moment_nm: float


class ReportArmResult(CamelBaseModel):
    """Hasil satu lengan. Tidak bergantung posisi cek maupun wind case."""
    name: str
    specification: ReportArmSpecification
    loads: list[ReportArmLoad]
    total_fix_load_n: float
    total_fix_load_moment_nm: float
    total_wind_moment_nm: float
    bending_moment_nm: float
    calculated_stress_n_mm2: float
    allowable_stress_n_mm2: float
    utilization_ratio: float
    status: CheckStatus


class ReportOverheadWireResult(CamelBaseModel):
    """Hasil satu kawat udara pada wind case laporan."""
    name: str
    wind_coefficient: float
    fix_load_per_length_n_m: float
    fixed_tension_n: float
    combined_wind_line_load_n_m: float
    wind_tension_n: float


# ===== Header laporan =====
ReportText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OptionalReportText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]


class ReportHeaderWrite(CamelBaseModel):
    """Body PUT: mengganti seluruh header. Field opsional yang tidak dikirim menjadi kosong."""
    region_code_id: str
    department_code_id: str | None = None
    author_code_id: str | None = None
    report_number: ReportText
    design_request_management_no: ReportText
    report_title_1: ReportText
    report_title_2: OptionalReportText | None = None
    report_title_3: OptionalReportText | None = None

    @field_validator("report_title_2", "report_title_3")
    @classmethod
    def _blank_title_is_empty(cls, value: str | None) -> str | None:
        # Form mengirim "" untuk baris judul yang tidak dipakai.
        return value or None


class ReportHeaderCode(CamelBaseModel):
    id: str
    code: str
    label: str


class ReportHeaderRead(CamelBaseModel):
    calculation_case_id: str
    region_code: ReportHeaderCode
    department_code: ReportHeaderCode | None = None
    author_code: ReportHeaderCode | None = None
    report_number: str
    design_request_management_no: str
    report_title_1: str
    report_title_2: str | None = None
    report_title_3: str | None = None
    updated_at: datetime


class CalculationReport(CamelBaseModel):
    # None untuk preview Project Tools: dihitung tanpa run tersimpan.
    run_id: str | None = None
    # Header milik case saat dibaca (tabel reports), bukan bagian run. None bila belum diisi.
    header: ReportHeaderRead | None = None
    template: str
    design_standard_code: int
    design_standard_name: str
    # Wind case yang ditampilkan di bagian pemeriksaan.
    wind_case: str
    design_wind_speed_m_s: float
    wind_pressure_n_m2: float
    allowable_stress_n_mm2: float
    geometry: ReportGeometry
    # Step pole dari puncak tertinggi seperti geometry.step_poles, lalu lengan urut nama
    # seperti geometry.arms.
    specifications: list[ReportSpecification]
    # Urut dari posisi cek tertinggi.
    sections: list[ReportSection]
    foundation: ReportFoundationLoads
    overall: ReportOverallCheck
    arms: list[ReportArmResult]
    overhead_wires: list[ReportOverheadWireResult]


# ===== Run =====
class CalculationRunContext(CamelBaseModel):
    """input_snapshot.context: nilai yang dipakai saat run dibuat, bukan nilai sekarang.
    Pasangan staleCauses: menunjukkan apa yang berbeda dari isian dan kondisi sekarang."""
    design_standard_id: str
    design_standard_name: str
    design_standard_code: int
    wind_speed: float | None = None
    air_density: float
    pole_standard_id: str
    pole_standard_name: str
    pole_standard_height_id: str
    pole_standard_height: float
    ground_position: GroundPosition
    gl_elevation_m: float | None = None
    embedment_length_mm: float | None = None


# Alasan run terbaru tidak lagi menggambarkan isian atau kondisi request (builder.run_stale_causes).
StaleCause = Literal["input", "conditions"]


class CalculationRunRead(CamelBaseModel):
    """GET .../runs: run terbaru case. Snapshot mentah tetap di database dan dibaca laporan."""
    id: str
    status: StatusCalculationRun
    utilization_ratio: float | None = None
    run_at: datetime
    run_by_user_id: str
    context: CalculationRunContext
    # Disusun saat dibaca, tidak disimpan. None untuk run failed.
    display: CalculationDisplay | None = None
    # Jawaban penolakan Calculation Service. Hanya terisi untuk run failed.
    error_snapshot: dict[str, Any] | None = None
    # Kosong = run masih menggambarkan isian dan kondisi sekarang.
    stale_causes: list[StaleCause]


class RunNotCreated(CamelBaseModel):
    reason: str
    message: str


class CalculationSaveResult(CamelBaseModel):
    """Jawaban Simpan. Run dibuat: run_id dan status terisi. Tidak dibuat: run_not_created."""
    run_id: str | None = None
    status: StatusCalculationRun | None = None
    run_not_created: RunNotCreated | None = None


# ===== Draft isian perhitungan =====
# Kunci yang boleh ada di draft: field CalculationInput dalam camelCase, tanpa recopyCatalog
# (aksi Simpan, bukan isian). Nilainya tidak divalidasi: draft boleh setengah jadi.
CALCULATION_DRAFT_KEYS = frozenset({
    "poleStandardHeightId",
    "directObjects",
    "overheadWires",
    "arms",
    "groundPosition",
    "embedmentLengthMm",
})
# Batas ukuran draft dalam byte JSON.
CALCULATION_DRAFT_MAX_BYTES = 256 * 1024


class CalculationDraftRead(CamelBaseModel):
    input: dict[str, Any]
    saved_at: datetime


class CalculateResult(CamelBaseModel):
    """Hasil Hitung: status dan tampilan hasil. Payload dan jawaban mentah ada di run (Simpan)."""
    status: StatusCalculationRun
    display: CalculationDisplay