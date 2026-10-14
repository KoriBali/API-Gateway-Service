from datetime import datetime, date

from pydantic import Field, model_validator

from app.utils.base_schema import CamelBaseModel
from app.database.models.intake import (
    BrandLine,
    RequestStatus,
    RequestType,
    DesignType,
    RequestClassification,
    DesignOrigin,
)
from app.database.models.calculation_object import FoundationType
from app.modules.assignment.schemas import AssignmentCreate
from app.database.models.drawing import (
    DrawingType,
    SurfaceTreatmentOption,
    PlatingType,
    PaintingType,
)


# design_type yang memuat pekerjaan gambar. Request seperti ini wajib mengisi
# sharedDetails.regionId dan sharedDetails.drawingType.
DRAWING_DESIGN_TYPES = frozenset({DesignType.drawing, DesignType.drawing_calculation})


def _reject_null(model: CamelBaseModel, fields: tuple[str, ...]):
    """Tolak `null` eksplisit untuk kolom wajib (422, bukan 500 dari DB)."""
    for field in fields:
        if field in model.model_fields_set and getattr(model, field) is None:
            raise ValueError(f"{type(model).model_fields[field].alias or field} cannot be null")
    return model



# ===== Project =====
class ProjectCreate(CamelBaseModel):
    request_form: BrandLine
    scope_code: str = Field(default="", max_length=50)
    pj_no: str = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _check_scope_code(self):
        if self.request_form == BrandLine.ys and self.scope_code != "":
            raise ValueError("scopeCode must be empty for a YS project")
        if self.request_form == BrandLine.yp and self.scope_code == "":
            raise ValueError("scopeCode is required for a YP project")
        return self



# ===== Tabel tambahan, finish, conditions (dipakai create dan patch) =====
class SharedDetailsWrite(CamelBaseModel):
    scheduled_delivery_date: str | None = Field(default=None, max_length=100)
    delivery_quantity: int | None = Field(default=None, ge=0)
    requester_pic_name: str | None = Field(default=None, max_length=120)
    region_id: str | None = Field(default=None, min_length=1)
    drawing_type: DrawingType | None = None
    # Teks berpilihan: label Inggris dari form (None, A1, ..., DXF, DWG) atau isian bebas.
    paper_size: str | None = Field(default=None, max_length=50)
    is_cad_data_requested: bool | None = None
    cad_format: str | None = Field(default=None, max_length=50)


# requesting_department_code nullable di DB, tetapi wajib di form intake YP.
_YP_NOT_NULL = (
    "requesting_department_code",
    "calc_strength", "calc_design",
    "scope_main_member", "scope_joint", "scope_foundation",
    "drafting_tracing", "drafting_design",
)


class YpDetailsWrite(CamelBaseModel):
    requesting_department_code: str | None = Field(default=None, min_length=1, max_length=50)
    record_no: str | None = Field(default=None, max_length=100)
    department_code: str | None = Field(default=None, max_length=50)
    brand_mark: BrandLine | None = None
    tail_code: str | None = Field(default=None, max_length=10)
    calc_strength: bool | None = None
    calc_design: bool | None = None
    scope_main_member: bool | None = None
    scope_joint: bool | None = None
    scope_foundation: bool | None = None
    scope_other: str | None = Field(default=None, max_length=200)
    drafting_tracing: bool | None = None
    drafting_design: bool | None = None
    submission_destination_1: str | None = Field(default=None, max_length=200)
    submission_destination_2: str | None = Field(default=None, max_length=200)
    submission_destination_3: str | None = Field(default=None, max_length=200)
    has_competitor: bool | None = None
    design_origin: DesignOrigin | None = None
    # Teks berpilihan: label Inggris dari form atau isian bebas.
    schedule_flexibility: str | None = Field(default=None, max_length=200)
    paper_frame: str | None = Field(default=None, max_length=100)
    finished_copies: int | None = Field(default=None, ge=0)
    plating_proviso: str | None = None

    @model_validator(mode="after")
    def _not_null(self):
        return _reject_null(self, _YP_NOT_NULL)


class YsDetailsWrite(CamelBaseModel):
    receipt_no: str | None = Field(default=None, max_length=100)
    # Field intake
    material_text: str | None = Field(default=None, max_length=200)
    material_id: str | None = Field(default=None, min_length=1)
    foundation_type: FoundationType | None = None
    foundation_width_x: float | None = Field(default=None, gt=0)
    foundation_width_y: float | None = Field(default=None, gt=0)
    embedment_depth: float | None = Field(default=None, gt=0)
    # Referensi
    design_standard_text: str | None = Field(default=None, max_length=200)
    opening_height: str | None = Field(default=None, max_length=100)
    concrete_strength: str | None = Field(default=None, max_length=200)
    # Catatan
    opening_direction_note: str | None = None


class FinishWrite(CamelBaseModel):
    treatment_option: SurfaceTreatmentOption | None = None
    plating_type: PlatingType | None = None
    plating_spec: str | None = Field(default=None, max_length=100)
    painting_type: PaintingType | None = None
    color_name: str | None = Field(default=None, max_length=100)
    munsell_value: str | None = Field(default=None, max_length=50)
    color_code: str | None = Field(default=None, max_length=50)


class ConditionsCreate(CamelBaseModel):
    design_standard_id: str = Field(min_length=1)
    wind_speed: float | None = None
    air_density: float


class ConditionsUpdate(CamelBaseModel):
    design_standard_id: str | None = Field(default=None, min_length=1)
    wind_speed: float | None = None
    air_density: float | None = None

    @model_validator(mode="after")
    def _not_null(self):
        return _reject_null(self, ("design_standard_id", "air_density"))



# ===== Request =====
# request_no, subject, due_date nullable di DB tetapi wajib di form intake.
_REQUEST_NOT_NULL = (
    "pole_category_id", "request_no", "pj_no", "request_type", "design_type",
    "request_classification", "subject", "request_date", "due_date",
    "requesting_department_name",
)


class RequestCreate(CamelBaseModel):
    brand_line: BrandLine
    project_id: str | None = Field(default=None, min_length=1)
    pole_category_id: str = Field(min_length=1)

    request_no: str = Field(min_length=1, max_length=100)
    pj_no: str = Field(min_length=1, max_length=100)

    request_type: RequestType
    design_type: DesignType
    request_classification: RequestClassification

    subject: str = Field(min_length=1, max_length=200)
    request_date: date
    due_date: date
    requesting_department_name: str = Field(min_length=1, max_length=200)
    notes: str | None = None

    shared_details: SharedDetailsWrite | None = None
    yp_details: YpDetailsWrite | None = None
    ys_details: YsDetailsWrite | None = None
    finish: FinishWrite | None = None
    conditions: ConditionsCreate
    assignments: list[AssignmentCreate] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _check_form(self):
        if self.brand_line == BrandLine.yp and self.ys_details is not None:
            raise ValueError("ysDetails is only allowed for a YS request")
        if self.brand_line == BrandLine.ys and self.yp_details is not None:
            raise ValueError("ypDetails is only allowed for a YP request")
        if self.brand_line == BrandLine.yp and (
            self.yp_details is None or self.yp_details.requesting_department_code is None
        ):
            raise ValueError("ypDetails.requestingDepartmentCode is required for a YP request")
        if self.design_type in DRAWING_DESIGN_TYPES and (
            self.shared_details is None
            or self.shared_details.region_id is None
            or self.shared_details.drawing_type is None
        ):
            raise ValueError(
                "sharedDetails.regionId and sharedDetails.drawingType are required "
                "when designType includes drawing"
            )
        return self


class RequestUpdate(CamelBaseModel):
    # brand_line sengaja tidak ada: form dikunci sejak request dibuat.
    project_id: str | None = Field(default=None, min_length=1)
    pole_category_id: str | None = Field(default=None, min_length=1)
    request_no: str | None = Field(default=None, min_length=1, max_length=100)
    pj_no: str | None = Field(default=None, min_length=1, max_length=100)
    request_type: RequestType | None = None
    design_type: DesignType | None = None
    request_classification: RequestClassification | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    request_date: date | None = None
    due_date: date | None = None
    requesting_department_name: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = None

    @model_validator(mode="after")
    def _not_null(self):
        return _reject_null(self, _REQUEST_NOT_NULL)



# ===== Output =====
class ProjectRead(CamelBaseModel):
    id: str
    request_form: BrandLine
    scope_code: str
    pj_no: str
    is_placeholder: bool


class SharedDetailsRead(CamelBaseModel):
    id: str
    scheduled_delivery_date: str | None = None
    delivery_quantity: int | None = None
    requester_pic_name: str | None = None
    region_id: str | None = None
    drawing_type: DrawingType | None = None
    paper_size: str | None = None
    is_cad_data_requested: bool | None = None
    cad_format: str | None = None


class YpDetailsRead(CamelBaseModel):
    id: str
    requesting_department_code: str | None = None
    record_no: str | None = None
    department_code: str | None = None
    brand_mark: BrandLine | None = None
    tail_code: str | None = None
    calc_strength: bool
    calc_design: bool
    scope_main_member: bool
    scope_joint: bool
    scope_foundation: bool
    scope_other: str | None = None
    drafting_tracing: bool
    drafting_design: bool
    submission_destination_1: str | None = None
    submission_destination_2: str | None = None
    submission_destination_3: str | None = None
    has_competitor: bool | None = None
    design_origin: DesignOrigin | None = None
    schedule_flexibility: str | None = None
    paper_frame: str | None = None
    finished_copies: int | None = None
    plating_proviso: str | None = None


class YsDetailsRead(CamelBaseModel):
    id: str
    receipt_no: str | None = None
    material_text: str | None = None
    material_id: str | None = None
    foundation_type: FoundationType | None = None
    foundation_width_x: float | None = None
    foundation_width_y: float | None = None
    embedment_depth: float | None = None
    design_standard_text: str | None = None
    opening_height: str | None = None
    concrete_strength: str | None = None
    opening_direction_note: str | None = None


class FinishRead(CamelBaseModel):
    id: str
    treatment_option: SurfaceTreatmentOption | None = None
    plating_type: PlatingType | None = None
    plating_spec: str | None = None
    painting_type: PaintingType | None = None
    color_name: str | None = None
    munsell_value: str | None = None
    color_code: str | None = None


class ConditionsRead(CamelBaseModel):
    id: str
    design_standard_id: str
    wind_speed: float | None = None
    air_density: float


class RequestRead(CamelBaseModel):
    id: str
    brand_line: BrandLine
    project_id: str | None = None
    responsible_department_id: str
    created_by_user_id: str
    pole_category_id: str
    status: RequestStatus
    request_no: str | None = None
    pj_no: str
    request_type: RequestType
    design_type: DesignType
    request_classification: RequestClassification
    subject: str | None = None
    request_date: date
    due_date: date | None = None
    requesting_department_name: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class RequestDetailRead(RequestRead):
    shared_details: SharedDetailsRead | None = None
    yp_details: YpDetailsRead | None = None
    ys_details: YsDetailsRead | None = None
    finish: FinishRead | None = None
    conditions: ConditionsRead | None = None



# ===== Cek nomor request (図番 YP) =====
class RequestNoSegments(CamelBaseModel):
    scope_code: str
    tail_code: str
    pj_no: str
    record_no: str | None = None


class RequestNoDuplicate(CamelBaseModel):
    id: str
    brand_line: BrandLine
    status: RequestStatus
    subject: str | None = None
    created_at: datetime


class RequestNoCheckRead(CamelBaseModel):
    request_no: str
    matches_pattern: bool
    segments: RequestNoSegments | None = None
    project_id: str | None = None
    warnings: list[str]
    duplicate_count: int
    duplicates: list[RequestNoDuplicate]