import uuid
import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
# Tipe bersama: satu konsep satu tipe, dipakai ulang dari sisi case.
from app.database.models.calculation_object import FoundationType
from app.database.models.drawing import (
    DrawingType,
    SurfaceTreatmentOption,
    PlatingType,
    PaintingType,
)

if TYPE_CHECKING:
    from app.database.models.identity import Department, User
    from app.database.models.calculation import CalculationCase, Condition
    from app.database.models.drawing import DrawingCase



# ===== Enums =====
class BrandLine(str, enum.Enum):
    yp = "yp"
    ys = "ys"


class RequestStatus(str, enum.Enum):
    internal = "internal"
    prevention_check = "prevention_check"
    submitted = "submitted"
    cleared = "cleared"
    canceled = "canceled"


class RequestType(str, enum.Enum):
    general = "general"
    special = "special"


class DesignType(str, enum.Enum):
    drawing = "drawing"
    calculation = "calculation"
    drawing_calculation = "drawing_calculation"


class RequestClassification(str, enum.Enum):
    new = "new"
    change = "change"
    reuse_new = "reuse_new"


class DesignOrigin(str, enum.Enum):
    development = "development"
    proposal = "proposal"
    existing = "existing"
    customer_spec = "customer_spec"



# ===== Databank Project =====
class DatabankProject(Base):
    __tablename__ = "databank_projects"
    __table_args__ = (
        # For Foreign Key Composite
        UniqueConstraint(
            "id",
            "request_form",
            name="uq_databank_projects_id_request_form"),

        CheckConstraint(
            "request_form <> 'ys' OR scope_code = ''",
            name="ys_scope_code_empty"),

        Index(
            "uq_databank_projects_identity",
            "request_form", "scope_code", "pj_no",
            unique=True,
            postgresql_where=text("is_placeholder = false")),

    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    request_form: Mapped[BrandLine] = mapped_column(
        Enum(BrandLine),
        nullable=False,
    )

    scope_code: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    pj_no: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    is_placeholder: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )



# ===== Request =====
class Request(Base):
    """Inti intake saja. Field cover lain ada di
    request_shared_details, request_yp_details, dan request_ys_details."""
    __tablename__ = "requests"
    __table_args__ = (
        # Penopang FK komposit dari request_yp_details / request_ys_details.
        UniqueConstraint("id", "brand_line", name="uq_requests_id_brand_line"),
        # Request di dalam project wajib berform sama dengan project-nya.
        # project_id NULL (request General Affairs) tidak diperiksa (MATCH SIMPLE).
        ForeignKeyConstraint(
            ["project_id", "brand_line"],
            ["databank_projects.id", "databank_projects.request_form"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="fk_requests_project_id_databank_projects",
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    brand_line: Mapped[BrandLine] = mapped_column(
        Enum(BrandLine),
        nullable=False,
    )

    project_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    responsible_department_id: Mapped[str] = mapped_column(
        ForeignKey(
            "departments.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )

    created_by_user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )

    pole_category_id: Mapped[str] = mapped_column(
        ForeignKey(
            "pole_categories.id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus),
        default=RequestStatus.internal,
        server_default=RequestStatus.internal.value,
        nullable=False,
    )

    # 図番 utuh (YP) atau 依頼No (YS). Nullable di DB, wajib di API.
    request_no: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    pj_no: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    request_type: Mapped[RequestType] = mapped_column(
        Enum(RequestType),
        nullable=False,
    )

    design_type: Mapped[DesignType] = mapped_column(
        Enum(DesignType),
        nullable=False,
    )

    request_classification: Mapped[RequestClassification] = mapped_column(
        Enum(RequestClassification),
        nullable=False,
    )

    subject: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    request_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    requesting_department_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Child
    created_by_user: Mapped["User"] = relationship(
        back_populates="requests",
    )

    responsible_department: Mapped["Department"] = relationship(
        back_populates="requests",
    )

    # Parent
    conditions: Mapped["Condition | None"] = relationship(
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    shared_details: Mapped["RequestSharedDetails | None"] = relationship(
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    finish: Mapped["RequestFinish | None"] = relationship(
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Ekstensi form: FK-nya komposit (request_id, brand_line), jadi relasi ini
    # hanya untuk membaca. Baris ekstensi ditulis eksplisit di repository dan
    # dihapus oleh ON DELETE CASCADE di DB.
    yp_details: Mapped["RequestYpDetails | None"] = relationship(
        primaryjoin="Request.id == foreign(RequestYpDetails.request_id)",
        uselist=False,
        viewonly=True,
    )

    ys_details: Mapped["RequestYsDetails | None"] = relationship(
        primaryjoin="Request.id == foreign(RequestYsDetails.request_id)",
        uselist=False,
        viewonly=True,
    )

    calculation_cases: Mapped[list["CalculationCase"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    drawing_cases: Mapped[list["DrawingCase"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )



# ===== Request Shared Details =====
class RequestSharedDetails(Base):
    """Field cover yang tercetak di form YP DAN YS. Tanpa kolom penjaga (milik kedua form)."""
    __tablename__ = "request_shared_details"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Waktu kirim TIANG ke pelanggan (納入予定日 / 納入時期), teks bebas mis. "3/末".
    # Walau berakhiran _date, kolom ini varchar: jangan diparse atau diurutkan sebagai tanggal.
    scheduled_delivery_date: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requester_pic_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # region_id dan drawing_type wajib di API bila design_type memuat drawing
    region_id: Mapped[str | None] = mapped_column(
        ForeignKey("regions.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    drawing_type: Mapped[DrawingType | None] = mapped_column(         # default -> drawing_cases.drawing_type
        Enum(DrawingType),
        nullable=True,
    )

    paper_size: Mapped[str | None] = mapped_column(String, nullable=True)
    # Nullable dengan sengaja: belum diisi berbeda dari 不要 (false).
    is_cad_data_requested: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cad_format: Mapped[str | None] = mapped_column(String, nullable=True)

    # Child
    request: Mapped["Request"] = relationship(
        back_populates="shared_details",
    )



# ===== Request YP Details =====
class RequestYpDetails(Base):
    __tablename__ = "request_yp_details"
    __table_args__ = (
        ForeignKeyConstraint(
            ["request_id", "brand_line"],
            ["requests.id", "requests.brand_line"],
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_request_yp_details_request_id_requests",
        ),
        # Kolom penjaga: baris ini hanya boleh menempel ke request YP.
        CheckConstraint("brand_line = 'yp'", name="brand_line_yp"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
    )

    brand_line: Mapped[BrandLine] = mapped_column(
        Enum(BrandLine),
        default=BrandLine.yp,
        nullable=False,
    )

    # Kode kantor peminta (依頼部署). Nullable di DB, wajib di API untuk request YP.
    requesting_department_code: Mapped[str | None] = mapped_column(String, nullable=True)
    record_no: Mapped[str | None] = mapped_column(String, nullable=True)
    department_code: Mapped[str | None] = mapped_column(String, nullable=True)

    brand_mark: Mapped[BrandLine | None] = mapped_column(
        Enum(BrandLine),
        nullable=True,
    )

    # Tail 図番 apa adanya (PJ, YS, JP, ...). Tidak pernah mengisi / diisi dari brand_mark.
    tail_code: Mapped[str | None] = mapped_column(String, nullable=True)

    # Blok 依頼区分: satu boolean per kotak centang. Tidak pernah dibaca logika sistem.
    calc_strength: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    calc_design: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scope_main_member: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scope_joint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scope_foundation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scope_other: Mapped[str | None] = mapped_column(String, nullable=True)
    drafting_tracing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    drafting_design: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    submission_destination_1: Mapped[str | None] = mapped_column(String, nullable=True)
    submission_destination_2: Mapped[str | None] = mapped_column(String, nullable=True)
    submission_destination_3: Mapped[str | None] = mapped_column(String, nullable=True)

    # Nullable dengan sengaja: belum diisi berbeda dari dipilih 無 (false).
    has_competitor: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    design_origin: Mapped[DesignOrigin | None] = mapped_column(
        Enum(DesignOrigin),
        nullable=True,
    )

    # Teks berpilihan: label Inggris atau isian bebas.
    schedule_flexibility: Mapped[str | None] = mapped_column(String, nullable=True)
    paper_frame: Mapped[str | None] = mapped_column(String, nullable=True)

    finished_copies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plating_proviso: Mapped[str | None] = mapped_column(Text, nullable=True)



# ===== Request YS Details =====
class RequestYsDetails(Base):
    __tablename__ = "request_ys_details"
    __table_args__ = (
        ForeignKeyConstraint(
            ["request_id", "brand_line"],
            ["requests.id", "requests.brand_line"],
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_request_ys_details_request_id_requests",
        ),
        # Kolom penjaga: baris ini hanya boleh menempel ke request YS.
        CheckConstraint("brand_line = 'ys'", name="brand_line_ys"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
    )

    brand_line: Mapped[BrandLine] = mapped_column(
        Enum(BrandLine),
        default=BrandLine.ys,
        nullable=False,
    )

    # Identitas: 受付No, external reference.
    receipt_no: Mapped[str | None] = mapped_column(String, nullable=True)

    material_text: Mapped[str | None] = mapped_column(String, nullable=True)
    material_id: Mapped[str | None] = mapped_column(          # default -> step_poles.material_id
        ForeignKey("materials.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    foundation_type: Mapped[FoundationType | None] = mapped_column(   # default -> calculation_foundations.type
        Enum(FoundationType),
        nullable=True,
    )
    # Pondasi bulat: diameter disimpan di foundation_width_x.
    foundation_width_x: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)  # default, square saja
    foundation_width_y: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)  # default, square saja
    embedment_depth: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)     # default

    # Referensi: apa adanya dari cover, tidak pernah memasok default.
    design_standard_text: Mapped[str | None] = mapped_column(String, nullable=True)
    opening_height: Mapped[str | None] = mapped_column(String, nullable=True)
    concrete_strength: Mapped[str | None] = mapped_column(String, nullable=True)

    # Catatan: tidak pernah dibaca sistem.
    opening_direction_note: Mapped[str | None] = mapped_column(Text, nullable=True)



# ===== Request Finish =====
class RequestFinish(Base):
    """Finish yang DIMINTA. Bentuk kolomnya meniru drawing_surfaces (finish yang DIGAMBAR)."""
    __tablename__ = "request_finish"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        unique=True,
    )

    treatment_option: Mapped[SurfaceTreatmentOption | None] = mapped_column(
        Enum(SurfaceTreatmentOption),
        nullable=True,
    )

    #   bila ternyata ada request yang meminta lebih dari satu cat / warna.
    plating_type: Mapped[PlatingType | None] = mapped_column(
        Enum(PlatingType),
        nullable=True,
    )
    plating_spec: Mapped[str | None] = mapped_column(String, nullable=True)
    painting_type: Mapped[PaintingType | None] = mapped_column(
        Enum(PaintingType),
        nullable=True,
    )
    color_name: Mapped[str | None] = mapped_column(String, nullable=True)
    munsell_value: Mapped[str | None] = mapped_column(String, nullable=True)
    color_code: Mapped[str | None] = mapped_column(String, nullable=True)

    # Child
    request: Mapped["Request"] = relationship(
        back_populates="finish",
    )