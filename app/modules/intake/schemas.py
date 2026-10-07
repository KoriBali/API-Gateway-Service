from datetime import datetime, date

from pydantic import Field, model_validator

from app.utils.base_schema import CamelBaseModel
from app.database.models.intake import (
    BrandLine,
    RequestStatus,
    RequestType,
    DesignType,
    RequestClassification,
    PoleKind,
    DesignOrigin,
    ScheduleFlexibility,
    PaperFrame,
)
from app.database.models.calculation_object import FoundationType
from app.database.models.drawing import (
    DrawingType,
    SurfaceTreatmentOption,
    PlatingType,
    PaintingType,
)



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



# ===== Ekstensi form, design condition, finish (dipakai create dan patch) =====
# document_no nullable di DB, tetapi wajib di form intake YP (DD invariant intake 8).
_YP_NOT_NULL = (
    "document_no",
    "calc_strength", "calc_design",
    "scope_main_member", "scope_joint", "scope_foundation",
    "drafting_tracing", "drafting_design", "deliver_cad_data",
)


class YpDetailsWrite(CamelBaseModel):
    document_no: str | None = Field(default=None, min_length=1, max_length=100)
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
    deliver_cad_data: bool | None = None
    submission_destination_1: str | None = Field(default=None, max_length=200)
    submission_destination_2: str | None = Field(default=None, max_length=200)
    submission_destination_3: str | None = Field(default=None, max_length=200)
    has_competitor: bool | None = None
    design_origin: DesignOrigin | None = None
    schedule_flexibility: ScheduleFlexibility | None = None
    schedule_note: str | None = None
    paper_frame: PaperFrame | None = None
    finished_copies: int | None = Field(default=None, ge=0)
    plating_proviso: str | None = None

    @model_validator(mode="after")
    def _not_null(self):
        return _reject_null(self, _YP_NOT_NULL)


class YsDetailsWrite(CamelBaseModel):
    delivery_quantity: int | None = Field(default=None, ge=0)


class DesignConditionsWrite(CamelBaseModel):
    # Field intake
    material_text: str | None = Field(default=None, max_length=200)
    material_id: str | None = Field(default=None, min_length=1)
    foundation_type: FoundationType | None = None
    foundation_width_x: float | None = Field(default=None, gt=0)
    foundation_width_y: float | None = Field(default=None, gt=0)
    embedment_depth: float | None = Field(default=None, gt=0)
    drawing_type: DrawingType | None = None
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
_REQUEST_NOT_NULL = (
    "pole_category_id", "pj_no", "request_type", "design_type", "request_classification",
)


class RequestCreate(CamelBaseModel):
    brand_line: BrandLine
    project_id: str | None = Field(default=None, min_length=1)
    pole_category_id: str = Field(min_length=1)

    request_no: str | None = Field(default=None, max_length=100)
    receipt_no: str | None = Field(default=None, max_length=100)
    pj_no: str = Field(min_length=1, max_length=100)

    request_type: RequestType
    design_type: DesignType
    request_classification: RequestClassification
    pole_kind: PoleKind | None = None
    region_id: str | None = Field(default=None, min_length=1)

    requesting_department_code: str | None = Field(default=None, max_length=50)
    requesting_department_name: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=200)
    due_date: date | None = None
    request_date: date | None = None
    notes: str | None = None
    requester_pic_name: str | None = Field(default=None, max_length=120)
    document_delivery_target: str | None = Field(default=None, max_length=200)

    yp_details: YpDetailsWrite | None = None
    ys_details: YsDetailsWrite | None = None
    design_conditions: DesignConditionsWrite | None = None
    finish: FinishWrite | None = None
    conditions: ConditionsCreate

    @model_validator(mode="after")
    def _check_form(self):
        if self.brand_line == BrandLine.yp and self.ys_details is not None:
            raise ValueError("ysDetails is only allowed for a YS request")
        if self.brand_line == BrandLine.ys and self.yp_details is not None:
            raise ValueError("ypDetails is only allowed for a YP request")
        if self.brand_line == BrandLine.yp and (
            self.yp_details is None or self.yp_details.document_no is None
        ):
            raise ValueError("ypDetails.documentNo is required for a YP request")
        return self


class RequestUpdate(CamelBaseModel):
    # brand_line sengaja tidak ada: form dikunci sejak request dibuat.
    project_id: str | None = Field(default=None, min_length=1)
    pole_category_id: str | None = Field(default=None, min_length=1)
    request_no: str | None = Field(default=None, max_length=100)
    receipt_no: str | None = Field(default=None, max_length=100)
    pj_no: str | None = Field(default=None, min_length=1, max_length=100)
    request_type: RequestType | None = None
    design_type: DesignType | None = None
    request_classification: RequestClassification | None = None
    pole_kind: PoleKind | None = None
    region_id: str | None = Field(default=None, min_length=1)
    requesting_department_code: str | None = Field(default=None, max_length=50)
    requesting_department_name: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=200)
    due_date: date | None = None
    request_date: date | None = None
    notes: str | None = None
    requester_pic_name: str | None = Field(default=None, max_length=120)
    document_delivery_target: str | None = Field(default=None, max_length=200)

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


class YpDetailsRead(CamelBaseModel):
    id: str
    document_no: str | None = None
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
    deliver_cad_data: bool
    submission_destination_1: str | None = None
    submission_destination_2: str | None = None
    submission_destination_3: str | None = None
    has_competitor: bool | None = None
    design_origin: DesignOrigin | None = None
    schedule_flexibility: ScheduleFlexibility | None = None
    schedule_note: str | None = None
    paper_frame: PaperFrame | None = None
    finished_copies: int | None = None
    plating_proviso: str | None = None


class YsDetailsRead(CamelBaseModel):
    id: str
    delivery_quantity: int | None = None


class DesignConditionsRead(CamelBaseModel):
    id: str
    material_text: str | None = None
    material_id: str | None = None
    foundation_type: FoundationType | None = None
    foundation_width_x: float | None = None
    foundation_width_y: float | None = None
    embedment_depth: float | None = None
    drawing_type: DrawingType | None = None
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
    receipt_no: str | None = None
    pj_no: str
    request_type: RequestType
    design_type: DesignType
    request_classification: RequestClassification
    pole_kind: PoleKind | None = None
    region_id: str | None = None
    requesting_department_code: str | None = None
    requesting_department_name: str | None = None
    subject: str | None = None
    due_date: date | None = None
    request_date: date | None = None
    notes: str | None = None
    requester_pic_name: str | None = None
    document_delivery_target: str | None = None
    created_at: datetime
    updated_at: datetime


class RequestDetailRead(RequestRead):
    yp_details: YpDetailsRead | None = None
    ys_details: YsDetailsRead | None = None
    design_conditions: DesignConditionsRead | None = None
    finish: FinishRead | None = None
    conditions: ConditionsRead | None = None



# ===== Cek 図番 (document_no) =====
class DocumentNoSegments(CamelBaseModel):
    scope_code: str
    tail_code: str
    pj_no: str
    record_no: str | None = None


class DocumentNoDuplicate(CamelBaseModel):
    id: str
    status: RequestStatus
    subject: str | None = None
    created_at: datetime


class DocumentNoCheckRead(CamelBaseModel):
    document_no: str
    matches_pattern: bool
    segments: DocumentNoSegments | None = None
    project_id: str | None = None
    warnings: list[str]
    duplicate_count: int
    duplicates: list[DocumentNoDuplicate]